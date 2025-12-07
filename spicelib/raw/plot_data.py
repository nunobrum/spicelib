import logging
import dataclasses
import io
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Union

import numpy as np

from spicelib import SpiceReadException
from spicelib.editor.base_editor import scan_eng
from spicelib.log.logfile_data import try_convert_value
from spicelib.raw.plot_interface import PlotInterface, MIN_BYTES_IN_FILE
from spicelib.raw.raw_classes import Axis, TraceRead

from spicelib.utils.detect_encoding import detect_encoding, EncodingDetectError

_logger = logging.getLogger("spicelib.PlotData")

dtype_map = {
    'double': 'd',
    'complex': 'complex',
    'real': 'f'
}
inv_dtype_map = {v: k for k, v in dtype_map.items()}


def dtype_from_string(dtype_str: str) -> np.dtype:
    """Converts a string representation of a data type to a numpy dtype.

    :param dtype_str: The string representation of the data type
    :type dtype_str: str
    :return: The numpy dtype
    :rtype: np.dtype
    :raises ValueError: if the string representation is not recognized
    """
    if dtype_str in dtype_map:
        return np.dtype(dtype_map[dtype_str])
    else:
        raise ValueError(f"Invalid data type string: {dtype_str}")


@dataclasses.dataclass
class TraceInfo:
    """Class for holding trace information.
    This class is used to hold the information of a trace, including its name, type, and data.
    """
    name: str
    dtype: str
    var_type: str


def namify(spice_ref: str):
    """Translate from V(0,n01) to V__n01__ and I(R1) to I__R1__"""
    if spice_ref.lower() in ('time', 'frequency'):
        return spice_ref
    matchobj = re.match(r'(V|I|P)\((\w+)\)', spice_ref)
    if matchobj:
        return f'{matchobj.group(1)}__{matchobj.group(2)}__'
    else:
        raise NotImplementedError(f'Unrecognized alias type for alias : "{spice_ref}"')


def get_remaining_bytes(raw_file) -> int:
    current_pos = raw_file.tell()
    raw_file.seek(0, os.SEEK_END)
    bytes_remaining = raw_file.tell() - current_pos
    raw_file.seek(current_pos)
    return bytes_remaining


def raw_detect_encoding(raw_file: io.IOBase, header_offset=0) -> str:
    """Detects the encoding of the RAW file.

    :param raw_file: The file object to read from
    :type raw_file: io.BufferedReader
    :param header_offset: If applicable the offset on the file where the header is located
    :return: The encoding of the RAW file
    :rtype: str
    :raises EncodingDetectError: if the encoding cannot be detected
    """
    # I cannot use detectencoding() here, as that only works on real text files.
    # This may be a partially binary file, where that function breaks.

    raw_file.seek(header_offset)
    raw_line = raw_file.read(6)
    if len(raw_line) < 6:
        raise SpiceReadException("Invalid RAW file. File is too short to determine encoding.")
    try:
        line = raw_line.decode(encoding='utf_8')
    except UnicodeDecodeError:
        line = ''
    if line == 'Title:' or line == '\nTitle':
        answer = 'utf_8'
    else:
        try:
            line = raw_line.decode(encoding='utf_16_le')
        except UnicodeDecodeError:
            line = ''
        if line == 'Tit' or line == '\nTi':
            answer = 'utf_16_le'
        else:
            raise SpiceReadException("Invalid RAW file. Unrecognized encoding.")
    raw_file.seek(header_offset)  # reposition the pointer at the beginning of the header
    return answer


class PlotData(PlotInterface):
    """Class for holding plot data.
    This class is used to hold the data of a plot, including the axis and traces.

    Do not instantiate this class directly, use the ``RawRead`` class instead."""

    def __init__(self, raw_file: io.BufferedReader, raw_filename: Path, plot_nr: int, encoding: str,
                 dialect: Union[str, None], verbose: bool):
        """Initializes the PlotData object and reads the RAW file.

        :nodoc:

        This class is not intended to be documented by Sphinx. See RawRead for the parameters. """
        # Initialize and type the instance variables, for the documentation
        self._raw_filename = raw_filename
        self._plot_nr = plot_nr
        self._verbose = verbose
        self.header: list[str] = []  # List to store the header lines
        self._fpos_header = raw_file.tell()  # File position of the header section used to skip the data when reading the header.
        self._raw_params: OrderedDict = OrderedDict()  # Dictionary to store the raw parameters
        self._raw_params['Filename'] = raw_filename.as_posix()  # Storing the filename as part of the dictionary
        # TODO: use backannotations to store the backannotations
        self._backannotations = []  # Storing backannotations
        self._encoding = encoding if encoding else raw_detect_encoding(raw_file, self._fpos_header)  # Encoding of the RAW file, either 'utf_8' or 'utf_16_le'
        self._raw_type = None  # Type of the RAW file, either 'binary' or 'values' but initialized as None to indicate no data is available
        self._aliases = {}  # QSpice defines aliases for some of the traces that can be computed from other traces.
        self._spice_params = {}  # QSpice stores param values in the .raw file. They may have some usage later for
        self._nPoints = 0  # Number of points in the RAW file
        self._nVariables = 0  # Number of variables in the RAW file
        self._dialect = None  # The dialect of the RAW file, either 'ltspice', 'qspice', 'ngspice' or 'xyce'
        self._trace_info: list[TraceInfo] = []  # List of tuples with the trace name and type
        self._read_traces: dict[str, Union[Axis, TraceRead]] = {}
        self._steps = None
        self._axis = None  # Creating the axis
        self._has_axis = False  # Indicates if the RAW file has an axis.
        self._flags = []

        # mark the file position of the header section
        # self._fpos_header = raw_file.tell()

        # Check how many bytes are still available in the file
        bytes_remaining = get_remaining_bytes(raw_file)
        if self._verbose:
            _logger.debug(f"Plot nr {self._plot_nr}: {bytes_remaining} bytes remaining in file.")

        if bytes_remaining < MIN_BYTES_IN_FILE:
            _logger.warning(f"Plot nr {self._plot_nr}: Not enough bytes remaining in file. The plot does not exist or is incomplete.")
            raise SpiceReadException(f"Invalid RAW file. Plot nr {self._plot_nr}: Not enough bytes remaining in file. The plot does not exist.")

        if self._encoding in ['utf_16_le', 'utf-16']:
            # Detect the encoding of the file
            sz_enc = 2
        else:
            sz_enc = 1

        if self._verbose:
            _logger.debug(f"Plot nr. {self._plot_nr}: Reading the file with encoding: '{self._encoding}'")

        # Read the header section of the RAW file

        line = ""
        while True:
            ch = raw_file.read(sz_enc).decode(encoding=self._encoding, errors='replace')
            if len(ch) == 0:
                # End of file reached
                if self._verbose:
                    _logger.warning(f"Plot nr. {self._plot_nr}: End of file reached while reading the header.")
                # will raise an exception later
                break
            if ch == '\n':
                # read one line. must remove the \r
                # if self._encoding == 'utf_8':  # no idea why utf_16_le would not need that, but this 'if' was here
                line = line.rstrip('\r')
                self.header.append(line)
                if line.lower() in ('binary:', 'values:'):
                    self._raw_type = line.lower()
                    break
                line = ""
            else:
                line += ch
        self._fpos_data = raw_file.tell()  # File position of the data section, used to skip the header when reading the data.
        _logger.debug(f"Plot nr {self._plot_nr}: Finished reading header.")

        if not self.has_data:
            # No data found this may be valid in some dialects, but not in others,
            # Xyce can have a text section after the binary section, so we cannot raise an exception here
            # this will have to be handled by the caller.
            if self._verbose:
                _logger.info(f"Invalid RAW file. Plot nr. {self._plot_nr}: Header is incomplete.")
            return

        # computing the aliases.
        for line in self.header:
            if line.startswith('.'):  # This is either a .param or a .alias
                if line.startswith('.param'):
                    # This is a .param line which format as the following pattern ".param temp=27"
                    _, _, line = line.partition('.param')
                    k, _, v = line.partition('=')
                    self._spice_params[k.strip()] = v.strip()
                elif line.startswith('.alias'):
                    # This is a parameter line which format as the following pattern ".alias I(R2) (0.0001mho*V(n01,out))"
                    _, alias, formula = line.split(' ', 3)
                    self._aliases[alias.strip()] = formula.strip()
            else:
                # This is the typical RAW style parameter format <param>: <value>
                k, _, v = line.partition(':')
                if k.lower() == 'variables':
                    break
                self._raw_params[k.strip().title()] = v.strip()  # Store the parameter in the dictionary, in title case
        self._nPoints = int(self._raw_params['No. Points'], 10)
        self._nVariables = int(self._raw_params['No. Variables'], 10)
        if self._nPoints == 0 or self._nVariables == 0:
            raise SpiceReadException(f"Invalid RAW file. Plot nr. {self._plot_nr}: No points or variables found: Points: {self._nPoints}, Variables: {self._nVariables}.")

        self._has_axis = self._raw_params['Plotname'].lower() not in ('operating point', 'transfer function', 'integrated noise')

        # autodetect the dialect. This is not always possible
        autodetected_dialect = None
        if 'Command' in self._raw_params:
            if 'ltspice' in self._raw_params['Command'].lower():
                # Can be auto detected
                # binary types: depends on flag, see below
                autodetected_dialect = 'ltspice'
            if 'qspice' in self._raw_params['Command'].lower():
                # Can be auto detected
                # binary types: always double for time, complex for AC
                # see if I already saw an autodetected dialect
                if dialect is None and autodetected_dialect is not None:
                    _logger.warning(f"Plot nr. {self._plot_nr}: Dialect is ambiguous: '{self._raw_params['Command']}'. Using qspice.")
                autodetected_dialect = 'qspice'
            if 'ngspice' in self._raw_params['Command'].lower():
                # Can only be auto detected from ngspice 44 on, as before there was no "Command:"
                # binary types: always double for time, complex for AC
                # see if I already saw an autodetected dialect
                if dialect is None and autodetected_dialect is not None:
                    _logger.warning(f"Plot nr. {self._plot_nr}: Dialect is ambiguous: '{self._raw_params['Command']}'. Using ngspice.")
                autodetected_dialect = 'ngspice'
            if 'xyce' in self._raw_params['Command'].lower():
                # Cannot be auto detected yet (at least not on 7.9, where there is no "Command:")
                #  Flags: real (for time) and complex (for frequency)
                #  Binary types: always double for time, complex for AC
                #  and potentially a text (csv) section that follows, that can be ignored.
                # see if I already saw an autodetected dialect
                if dialect is None and autodetected_dialect is not None:
                    _logger.warning(f"Plot nr. {self._plot_nr}: Dialect is ambiguous: '{self._raw_params['Command']}'. Using xyce.")
                autodetected_dialect = 'xyce'

        if dialect:
            if autodetected_dialect is not None:
                if dialect != autodetected_dialect:
                    _logger.warning(f"Plot nr. {self._plot_nr}: Dialect specified as {dialect}, but the file seems to be from {autodetected_dialect}. Trying to read it anyway.")
        else:
            # no dialect given. Take the autodetected version
            dialect = autodetected_dialect

        # Do I have something?
        if not dialect:
            raise SpiceReadException(f"Invalid RAW file. Plot nr. {self._plot_nr}: file dialect is not specified and could not be auto detected.")

        # and tell the outside world
        self._dialect = dialect

        # set the specifics per dialect
        always_double = dialect != 'ltspice'  # qspice, ngspice and xyce use doubles for everything outside of AC files
        frequency_double = dialect == 'qspice'  # qspice uses double also for frequency for AC files

        # Compiling the raw file information based on the dialect
        self._steps = None
        self._flags = self._raw_params['Flags'].split()
        if 'complex' in self._raw_params['Flags'].lower() or self._raw_params['Plotname'].lower() == 'ac analysis':
            numerical_type = 'complex'
        else:
            if always_double:  # qspice, ngspice and xyce use doubles for everything outside of AC
                numerical_type = 'double'
            elif "double" in self._raw_params['Flags'].lower():  # LTspice: .options numdgt = 7 sets this flag for double precision
                numerical_type = 'double'
            else:
                numerical_type = 'real'
        i = self.header.index('Variables:')
        _logger.debug(f"Plot nr {self._plot_nr}: Header successfully parsed. Reading trace information...")

        # Construct the trace information list so to be used on the numpy structured array
        ivar = 0
        for line in self.header[i + 1:-1]:  # Parse the variable names
            line_elmts = line.lstrip().split('\t')
            if len(line_elmts) < 3:
                raise SpiceReadException(f"Invalid RAW file. Plot nr. {self._plot_nr}: Invalid line in the Variables section: {line}")
            name = line_elmts[1]
            var_type = line_elmts[2]
            if ivar == 0:  # If it has an axis, it should be always read
                if numerical_type == 'real':
                    # only ltspice gets here, in non AC
                    axis_numerical_type = 'double'  # LTSpice uses double for the first variable in .OP
                elif numerical_type == 'complex' and frequency_double:
                    axis_numerical_type = 'double'  # QSPICE uses double for frequency for .AC files
                else:
                    axis_numerical_type = numerical_type
                trace_info = TraceInfo(name, dtype_map[axis_numerical_type], var_type)
            else:
                trace_info = TraceInfo(name, dtype_map[numerical_type], var_type)
            self._trace_info.append(trace_info)
            ivar += 1

        if self._verbose:
            _logger.info(f"Plot nr. {self._plot_nr}: Plot is of type '{self.get_plot_name()}', contains {ivar} "
                         f"traces with {self._nPoints} points, reading {len(self._trace_info)} traces.")

        # Setting the properties in the proper format
        self._raw_params["Variables"] = [var.name for var in self._trace_info]

        # Finally, Check for Step Information
        if "stepped" in self._raw_params["Flags"].lower():
            if self._verbose:
                _logger.debug(f"Plot nr. {self._plot_nr}: RAW file has stepped data.")
            try:
                self._load_step_information(raw_filename)
            except SpiceReadException as err:
                _logger.warning(f"Plot nr. {self._plot_nr}: {str(err)}\nError in auto-detecting steps in '{raw_filename}'")
                if self._has_axis:
                    number_of_steps = 0
                    if self._axis is not None:
                        for v in self._axis.data:
                            if v == self._axis.data[0]:
                                number_of_steps += 1
                else:
                    number_of_steps = self._nPoints
                self._steps = [{'run': i + 1} for i in range(number_of_steps)]

        if self._verbose:
            _logger.info(f"Plot nr. {self._plot_nr}: Plot read successfully.")
        # if the file is binary, we need to move the file pointer to the end of the data section
        if self._raw_type == 'binary:':
            # now move the file pointer to the end of the data section, so that the next plot can be read
            record_size = sum([np.dtype(t.dtype).itemsize for t in self._trace_info])
            raw_file.seek(self._fpos_data + self._nPoints * record_size)
        elif self._raw_type == 'values:':
            # In this case for an ASCII file, it will not be lazy and will read all data.
            if self._verbose:
                _logger.debug(f"Plot nr. {self._plot_nr}: ASCII RAW File")
            self._read_ascii_vector(raw_file)

    def _read_ascii_vector(self, raw_file):
        # Create the traces read vector
        for trace_info in self._trace_info:
            if trace_info.name in self._aliases:
                # This is an alias, the data will be computed later
                continue

            # Create the traces for all the info
            trace_data = np.zeros(self._nPoints, dtype=trace_info.dtype)  # Pre-allocate array for speed

            if trace_info.name == self._trace_info[0].name and self._has_axis:
                # This is the axis trace
                self._axis = Axis(trace_info.name, trace_info.var_type, self._nPoints,
                                  inv_dtype_map[trace_info.dtype], trace_data)
                if self._steps is not None:
                    self._axis.set_steps(self._steps)
                self._read_traces[trace_info.name] = self._axis
            else:
                # Create trace object
                trace = TraceRead(trace_info.name, trace_info.var_type, self._nPoints, self._axis,
                                  inv_dtype_map[trace_info.dtype],
                                  trace_data)
                self._read_traces[trace_info.name] = trace

        # Will start the reading of ASCII Values
        for point in range(self._nPoints):
            var_index = 0
            while var_index < len(self._trace_info):
                line = raw_file.readline().decode(encoding=self._encoding, errors='ignore')
                if len(line) == 0:
                    raise SpiceReadException(
                        f"Invalid RAW file. Plot nr. {self._plot_nr}: Invalid data: end of file encountered too early")
                line = line.strip()
                if len(line) == 0:
                    continue  # skip empty lines
                if var_index == 0:
                    s_point, value = line.split("\t", 1)
                    if point != int(s_point):
                        raise SpiceReadException(
                            f"Invalid RAW file. Plot nr. {self._plot_nr}: Invalid data: point is not in sequence ({point} != {int(s_point)})")

                else:
                    value = line

                var = self._trace_info[var_index]
                if var.dtype == 'complex':
                    v = value.split(',')
                    if len(v) != 2:
                        raise SpiceReadException(
                            f"Invalid RAW file. Plot nr. {self._plot_nr}: Invalid data for trace {var.name}: {value} is not a complex value")
                    self._read_traces[var.name].data[point] = complex(float(v[0]), float(v[1]))
                else:
                    self._read_traces[var.name].data[point] = float(value)
                var_index += 1
        # Remaining empty lines if exist are ignored
        while True:
            cursor = raw_file.tell()
            line = raw_file.readline().strip()
            if len(line) != 0:
                raw_file.seek(cursor)  # go back to the beginning of the line
            else:
                break
        if self._verbose:
            _logger.debug(f"Plot nr {self._plot_nr}: ASCII data read successfully.")

    @property
    def has_data(self) -> bool:
        """Indicates if the plot has data."""
        return self._raw_type is not None

    @property
    def dialect(self) -> Union[str, None]:
        """The dialect of the RAW file, either 'ltspice', 'qspice', 'ngspice' or 'xyce'
        """
        return self._dialect

    @property
    def encoding(self) -> str:
        """The encoding of the RAW file, either 'utf_8' or 'utf_16_le'
        """
        return self._encoding

    @property
    def nVariables(self) -> int:
        """Number of variables in the RAW file
        """
        return self._nVariables

    @property
    def nPoints(self) -> int:
        """Number of points in the RAW file
        """
        return self._nPoints

    @property
    def raw_type(self) -> str:
        """The type of the RAW file, either 'binary:' or 'values:'"""
        return self._raw_type

    @property
    def aliases(self) -> dict[str, str]:
        """QSpice defines aliases for some of the traces that can be computed from other traces.
        """
        return self._aliases

    @property
    def backannotations(self) -> list[str]:
        """List to store the backannotations found in the RAW file header
        """
        return self._backannotations

    @property
    def has_axis(self) -> bool:
        """Indicates if the RAW file has an axis.
        This is True for all RAW file plots except for 'Operating Point', 'Transfer Function', and 'Integrated Noise'.
        """
        return self._has_axis

    @property
    def axis(self) -> Union[Axis, None]:
        """
        .. deprecated:: 1.4.5 Use `get_axis()` method instead.

        The axis of the RAW file, if it exists.
        """
        return self._axis

    @property
    def raw_params(self) -> OrderedDict:
        """
        .. deprecated:: 1.4.5 Use `get_raw_properties()` or `get_raw_property()` method instead.

        Dictionary to store the parameters found in the RAW file header.
        The keys are the parameter names, and the values are the parameter values.
        """
        return self._raw_params

    @property
    def flags(self) -> list[str]:
        """List of Flags that are used in this plot. See :doc:`../varia/raw_file` for details.
        """
        return self._flags

    @property
    def steps(self) -> Union[list[dict[str, int]], None]:
        """List of steps in the RAW file, if it exists.
        If the RAW file does not contain stepped data, this will be None.
        If the RAW file contains stepped data, this will be a list of step numbers.
        """
        return self._steps

    def get_raw_property(self, property_name=None) -> Union[str, dict[str, str]]:
        """
        Get a property. By default, it returns all properties defined in the RAW file.

        :param property_name: name of the property to retrieve. If None, all properties are returned.
        :type property_name: str
        :returns: Property object
        :rtype: str
        :raises: ValueError if the property doesn't exist
        """
        # the property name is case-insensitive, but the keys are stored in title case.
        if property_name is None:
            return self.get_raw_properties()
        elif property_name.title() in self._raw_params.keys():
            return self._raw_params[property_name.title()]
        else:
            raise ValueError("Invalid property. Use %s" % str(self._raw_params.keys()))

    def get_raw_properties(self) -> dict[str, str]:
        """
        Get all raw properties.

        :return: Dictionary of all raw properties
        :rtype: dict[str, str]
        """
        return self._raw_params

    def get_plot_name(self) -> str:
        """
        Returns the type of the plot read from the RAW file. Some examples:

        * 'AC Analysis',
        * 'DC transfer characteristic',
        * 'Operating Point',
        * 'Transient Analysis',
        * 'Transfer Function',
        * 'Noise Spectral Density',
        * 'Frequency Response Analysis',
        * 'Noise Spectral Density Curves',
        * 'Integrated Noise'

        :return: plot name
        :rtype: str
        """
        property_name = "Plotname"
        if property_name in self._raw_params.keys():
            return self._raw_params[property_name]
        else:
            return ""

    def get_trace_names(self) -> list[str]:
        """
        Returns a list of exiting trace names of the RAW file.

        :return: trace names
        :rtype: list[str]
        """
        # parsing the aliases needs to be done before implementing this.
        return self.raw_params['Variables'] + list(self._aliases.keys())

    def _compute_alias(self, alias: str) -> TraceRead:
        """
        Constants like mho need to be replaced and V(ref1,ref2) need to be replaced by (V(ref1)-V(ref2)) and after
        that the aliases can be computed, using the eval() function.
        """
        formula = self._aliases[alias]
        # converting V(ref1, ref2) to (V(ref1)-V(ref2))
        formula = re.sub(r'V\((\w+),0\)', r'V(\1)', formula)
        formula = re.sub(r'V\(0,(\w+)\)', r'(-V(\1))', formula)
        formula = re.sub(r'V\((\w+),(\w+)\)', r'(V(\1)-V(\2))', formula)
        # find all variables used in the formula
        used_vars = [var.name for var in self._trace_info if var.name in formula]
        # converting V(ref1) to V__ref1__ and I(ref1) to I__ref1__
        formula = re.sub(r'([VIP])\((\w+)\)', r'\1__\2__', formula)

        # removing the mho or other constants ex:  (0.0001mho*V(0,n01)) -> (0.0001*V(0,n01))
        formula = re.sub(r'(\d+)((mho)|(ohm))', r'\1', formula)
        if alias.startswith('I('):
            whattype = 'current'
        elif alias.startswith('V('):
            whattype = 'voltage'
        else:
            raise NotImplementedError(f'Unrecognized alias type for alias : "{alias}"')
        trace = TraceRead(alias, whattype, self._nPoints, self._axis, 'double')
        local_vars = {'pi': 3.1415926536, 'e': 2.7182818285}  # This is the dictionary that will be used to compute the alias
        local_vars.update({name: scan_eng(value) for name, value in self._spice_params.items()})
        self.read_trace_data(used_vars)
        local_vars.update({namify(name): self._read_traces[name].data for name in used_vars})
        try:
            trace.data = eval(formula, local_vars)
        except Exception as err:
            raise RuntimeError(f'Error computing alias "{alias}" with formula "{formula}"') from err
        return trace

    @staticmethod
    def _read_bytes_from_file(raw_file: io.BufferedReader, num_bytes: int) -> bytes:
        """Reads a specific number of bytes from a file.

        :param raw_file: The file object to read from
        :type raw_file: io.BufferedReader
        :param num_bytes: The number of bytes to read
        :type num_bytes: int
        :return: The bytes read from the file
        :rtype: bytes
        :raises SpiceReadException: if the number of bytes read is less than requested
        """
        data = raw_file.read(num_bytes)
        if len(data) < num_bytes:
            raise SpiceReadException("Invalid RAW file. Not enough data in the binary section.")
        return data

    def read_trace_data(self, list_of_traces: list[str]):
        """
        Reads the trace data from the binary section of the RAW file.
        """
        with open(self._raw_filename, 'rb') as raw_file:

            if self._raw_type == "binary:":
                # Will start the reading of binary values

                if "fastaccess" in self._raw_params["Flags"].lower():
                    if self._verbose:
                        _logger.debug(f"{self._raw_filename} Binary RAW file with Fast access")
                    # In Fast Accces mode, the data is already stored contiguously per trace

                    previous_data_size = 0
                    start_index = 0
                    # Always read the axis first, if it exists and was not read before
                    if self._has_axis and self._trace_info and (self._axis is None):
                        trace_info = self._trace_info[0]
                        start_index = 1
                        data_size = self._nPoints * np.dtype(trace_info.dtype).itemsize
                        # read this trace
                        raw_file.seek(self._fpos_data + previous_data_size)  # Move to the beginning of the data section
                        raw_data = self._read_bytes_from_file(raw_file, data_size)
                        assert len(raw_data) == data_size, "Invalid RAW file. Not enough data in the binary section."
                        previous_data_size += data_size
                        data = np.frombuffer(raw_data, dtype=trace_info.dtype)
                        # Now create the axis
                        num_type = inv_dtype_map[trace_info.dtype]
                        trace = Axis(trace_info.name, trace_info.var_type, self._nPoints, num_type, data)
                        self._axis = trace
                        self._read_traces[trace_info.name] = trace
                        if self._verbose:
                            _logger.debug(f"Axis '{trace.name}' read successfully. Data type: {trace_info.dtype}, First 5 values: {trace.data[:5]}")
                        # Set the steps if they exist
                        if self._steps is not None:
                            self._axis.set_steps(self._steps)

                    for trace_info in self._trace_info[start_index:]:
                        data_size = np.dtype(trace_info.dtype).itemsize * self._nPoints
                        if trace_info.name in list_of_traces:
                            # read this trace
                            raw_file.seek(self._fpos_data + previous_data_size)  # Move to the beginning of the data section
                            raw_data = self._read_bytes_from_file(raw_file, data_size)
                            assert len(raw_data) == data_size, "Invalid RAW file. Not enough data in the binary section."
                            data = np.frombuffer(raw_data, dtype=trace_info.dtype)
                            num_type = inv_dtype_map[trace_info.dtype]
                            # Now create the trace
                            trace = TraceRead(trace_info.name, trace_info.var_type, self._nPoints, self._axis, num_type, data)
                            self._read_traces[trace_info.name] = trace
                            if self._verbose:
                                _logger.debug(f"Binary data read successfully. Data shape: {data.shape}")
                        previous_data_size += data_size
                else:
                    # Normal Acccess
                    if self._verbose:
                        _logger.debug(f"{self._raw_filename} Binary RAW file with Normal access")

                    # create the numpy num_type for the structured array
                    read_dtypes = []
                    for i, trace_info in enumerate(self._trace_info):
                        if i == 0 and self._has_axis and (self._axis is None):
                            # Always read the axis first, if it exists and was not read before
                            read_dtypes.append((trace_info.name, trace_info.dtype))
                        elif trace_info.name in list_of_traces:
                            read_dtypes.append((trace_info.name, trace_info.dtype))
                        else:
                            # void num_type, to skip this trace
                            read_dtypes.append((trace_info.name, 'V' + str(np.dtype(trace_info.dtype).itemsize)))

                    if self._verbose:
                        _logger.debug(f"{self._raw_filename} Reading traces: {list_of_traces}")
                    record_size = sum([np.dtype(t.dtype).itemsize for t in self._trace_info])
                    raw_file.seek(self._fpos_data)  # Move to the beginning of the data section
                    raw_data = self._read_bytes_from_file(raw_file, self._nPoints * record_size)  # Move to the beginning of the data section
                    data = np.frombuffer(raw_data, dtype=read_dtypes)
                    if self._verbose:
                        _logger.debug(f"Binary data read successfully. Data shape: {data.shape}")
                    for i, trace_info in enumerate(self._trace_info):
                        if i == 0 and self._has_axis and (self._axis is None):
                            # Now create the axis
                            trace_data = data[trace_info.name]
                            num_type = inv_dtype_map[trace_info.dtype]
                            trace = Axis(trace_info.name, trace_info.var_type, self._nPoints, num_type, trace_data)
                            self._axis = trace
                            self._read_traces[trace_info.name] = trace
                            if self._verbose:
                                _logger.debug(f"Axis '{trace.name}' read successfully. Data type: {trace_info.dtype}, First 5 values: {trace.data[:5]}")
                            # Set the steps if they exist
                            if self._steps is not None:
                                self._axis.set_steps(self._steps)
                        elif trace_info.name in list_of_traces:
                            trace_data = data[trace_info.name]
                            num_type = inv_dtype_map[trace_info.dtype]
                            # Now create the trace
                            trace = TraceRead(trace_info.name, trace_info.var_type, self._nPoints, self._axis, num_type, trace_data)
                            self._read_traces[trace_info.name] = trace
                            if self._verbose:
                                _logger.debug(f"Trace '{trace.name}' read successfully. Data type: {trace_info.dtype}, First 5 values: {trace.data[:5]}")
            elif self._raw_type == "values:":
                pass  # nothing to do here, since the reading of ascii raw files is not lazy
            else:
                raise NotImplementedError("Only binary and value RAW files are supported at the moment.")

    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead]:
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        :raises IndexError: When a trace is not found
        """
        if isinstance(trace_ref, str):
            if trace_ref in self._read_traces:
                return self._read_traces[trace_ref]
            # not found directly, see if it's a case-insensitive match
            trace_ref_lower = trace_ref.casefold()
            for trace_name in self._read_traces:
                if trace_ref_lower == trace_name.casefold():  # The trace names are case-insensitive
                    # assert isinstance(trace, DataSet)
                    return self._read_traces[trace_name]
            # not found as a read trace, see if needs to be read from file
            try:
                index = self.raw_params['Variables'].index(trace_ref)
            except ValueError:
                for index, trace_info in enumerate(self._trace_info):
                    if trace_ref_lower == trace_info.name.casefold():  # The trace names are case-insensitive
                        break
                else:
                    index = -1
            if index >= 0:
                # need to read it from file
                trace_info = self._trace_info[index]
                self.read_trace_data([trace_info.name])
                return self._read_traces[trace_info.name]
            # see if it's an alias
            for alias in self._aliases:
                if trace_ref_lower == alias.casefold():
                    return self._compute_alias(alias)
            raise IndexError(f"{self} doesn't contain trace \"{trace_ref}\"\n"
                             f"Valid traces are {[trc.name for trc in self._trace_info]}")
        else:
            if trace_ref < 0 or trace_ref >= len(self._trace_info):
                raise IndexError(f"Trace index {trace_ref} out of range. Valid range is 0 to {len(self._trace_info)-1}.")
            trace_info = self._trace_info[trace_ref]
            return self.get_trace(trace_info.name)  # Recursion with a string

    def get_wave(self, trace_ref: Union[str, int], step: int = 0) -> np.ndarray:
        """
        Retrieves the trace data with the requested name (trace_ref), optionally providing the step number.

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :param step: Optional parameter specifying which step to retrieve.
        :type step: int
        :return: A numpy array containing the requested waveform.
        :rtype: numpy.array
        :raises IndexError: When a trace is not found
        """
        trace = self.get_trace(trace_ref)
        if isinstance(trace, Axis) or isinstance(trace, TraceRead):
            return trace.get_wave(step)
        else:
            raise IndexError(f"{self} doesn't contain trace \"{trace_ref}\"\n"
                             f"Valid traces are {[trc.name for trc in self._trace_info]}")

    def get_time_axis(self, step: int = 0) -> np.ndarray:
        """
        .. deprecated:: 1.0 Use `get_axis()` method instead.

        This function is equivalent to get_trace('time').get_time_axis(step) instruction.
        It's workaround on a LTSpice issue when using 2nd Order compression, where some values on
        the time trace have a negative value."""
        trace_ref = 'time'
        trace = self.get_trace(trace_ref)
        if isinstance(trace, Axis):
            return trace.get_time_axis(step)
        else:
            raise IndexError(f"{self} doesn't contain trace \"{trace_ref}\"\n"
                             f"Valid traces are {[trc.name for trc in self._trace_info]}")

    def get_axis(self, step: int = 0) -> Union[np.ndarray, list[float]]:
        """
        This function is equivalent to get_trace(0).get_wave(step) instruction.
        It also implements a workaround on a LTSpice issue when using 2nd Order compression, where some values on
        the time trace have a negative value.

        :param step: Step number, defaults to 0
        :type step: int, optional
        :raises RuntimeError: if the RAW file does not have an axis.
        :return: Array with the X axis
        :rtype: Union[np.ndarray, list[float]]
        """
        if self._axis:
            axis = self.get_trace(0)
            assert isinstance(axis, Axis), "This RAW file does not have an axis."
            return axis.get_wave(step)
        else:
            raise RuntimeError("This RAW file does not have an axis.")

    def get_len(self, step: int = 0) -> int:
        """
        Returns the length of the data at the give step index.

        :param step: the step index, defaults to 0
        :type step: int, optional
        :return: The number of data points
        :rtype: int
        """
        if self._axis is None:
            # If there is no axis, the length is the number of points
            return self._nPoints
        else:
            # If there is an axis, the length is the length of the axis at the given step
            assert isinstance(self._axis, Axis), "This RAW file does not have an axis."
            return self._axis.get_len(step)

    def _load_step_information(self, filename: Path):
        if 'Command' not in self._raw_params:
            # probably ngspice before v44 or xyce. And anyway, ngspice does not support the '.step' directive
            # FYI: ngspice can do something like .step via a control section with while loop.
            raise SpiceReadException("Unsupported simulator. Only LTspice and QSPICE are supported.")
        if not isinstance(self._raw_params['Command'], str):
            raise SpiceReadException("Invalid Command parameter. Expected a string.")

        if 'ltspice' in self._raw_params['Command'].lower():
            # look in the .log file for information about the steps
            if filename.suffix != '.raw':
                raise SpiceReadException("Invalid Filename. The file should end with '.raw'")
            # it should have a .log file with the same name
            logfile = filename.with_suffix(".log")
            try:
                encoding = detect_encoding(logfile, r"^((.*\n)?Circuit:|([\s\S]*)--- Expanded Netlist ---)")
                log = open(logfile, 'r', errors='replace', encoding=encoding)
            except OSError:
                raise SpiceReadException("Log file '%s' not found" % logfile)
            except UnicodeError:
                raise SpiceReadException("Unable to parse log file '%s'" % logfile)
            except EncodingDetectError:
                raise SpiceReadException("Unable to parse log file '%s'" % logfile)

            for line in log:
                if line.startswith(".step"):
                    step_dict = {}
                    for tok in line[6:-1].split(' '):
                        if '=' not in tok:
                            continue
                        key, value = tok.split('=')
                        step_dict[key] = try_convert_value(value)
                    if self._steps is None:
                        self._steps = [step_dict]
                    else:
                        self._steps.append(step_dict)
            log.close()

        elif 'qspice' in self._raw_params['Command'].lower():
            # look in the .log file for information about the steps
            if filename.suffix != '.qraw':
                raise SpiceReadException("Invalid Filename. The file should end with '.qraw'")
            # it should have a .log file with the same name
            logfile = filename.with_suffix(".log")
            try:
                log = open(logfile, 'r', errors='replace', encoding='utf-8')
            except OSError:
                raise SpiceReadException("Log file '%s' not found" % logfile)
            except UnicodeError:
                raise SpiceReadException("Unable to parse log file '%s'" % logfile)

            step_regex = re.compile(r"^(\d+) of \d+ steps:\s+\.step (.*)$")

            for line in log:
                match = step_regex.match(line)
                if match:
                    step_dict = {}
                    step = int(match.group(1))
                    stepset = match.group(2)
                    _logger.debug(f"Plot nr. {self._plot_nr}: Found step {step} with stepset {stepset}.")

                    tokens = stepset.strip('\r\n').split(' ')
                    for tok in tokens:
                        key, value = tok.split("=")
                        # Try to convert to int or float
                        step_dict[key] = try_convert_value(value)
                    if self._steps is None:
                        self._steps = [step_dict]
                    else:
                        self._steps.append(step_dict)
            log.close()

        else:
            raise SpiceReadException("Unsupported simulator. Only LTspice and QSPICE are supported.")

    def __getitem__(self, item):
        """Helper function to access traces by using the [ ] operator."""
        return self.get_trace(item)

    def get_steps(self, **kwargs) -> Union[list[int], range]:
        """Returns the steps that correspond to the query set in the `**kwargs` parameters.
        Example: ::

            raw_read.get_steps(V5=1.2, TEMP=25)

        This will return all steps in which the voltage source V5 was set to 1.2V and the TEMP parameter is 24 degrees.
        This feature is only possible if a .log file with the same name as the .raw file exists in the same directory.
        Note: the correspondence between step numbers and .STEP information is stored on the .log file.

        :key kwargs:
         key-value arguments in which the key correspond to a stepped parameter or source name, and the value is the
         stepped value.

        :return: The steps that match the query
        :rtype: list[int]
        """
        if self._steps is None:
            return [0]  # returns a single step
        else:
            if len(kwargs) > 0:
                ret_steps = []  # Initializing an empty array
                i = 0
                for step_dict in self._steps:
                    for key in kwargs:
                        ll = step_dict.get(key, None)
                        if ll is None:
                            break
                        elif kwargs[key] != ll:
                            break
                    else:
                        ret_steps.append(i)  # All the step parameters match
                    i += 1
                return ret_steps
            else:
                return range(len(self._steps))  # Returns all the steps

    def export(self, columns: Union[list, None] = None, step: Union[int, list[int]] = -1, **kwargs) -> dict[str, list]:
        """
        Returns a native python class structure with the requested trace data and steps.
        It consists of an ordered dictionary where the columns are the keys and the values are lists with the data.

        This function is used by the export functions.

        :param step: Step number to retrieve. If not given, it will return all steps
        :type step: int
        :param columns: List of traces to use as columns. Default is all traces
        :type columns: list
        :param kwargs: Additional arguments to pass to the pandas.DataFrame constructor
        :type kwargs: ``**dict``
        :return: A pandas DataFrame
        :rtype: pandas.DataFrame
        """
        if columns is None:
            columns = self.get_trace_names()  # if no columns are given, use all traces
        else:
            if self._axis and self._axis.name not in columns:  # If axis is not in the list, add it
                columns.insert(0, self._axis.name)

        if isinstance(step, list):
            steps_to_read = step  # If a list of steps is given, use it
        elif step == -1:
            steps_to_read = self.get_steps(**kwargs)  # If no step is given, read all steps
        else:
            steps_to_read = [step]  # If a single step is given, pass it as a list

        step_columns = []
        if len(step_columns) > 1:
            if self._steps is not None:
                for step_dict in self._steps[0]:
                    for key in step_dict:
                        step_columns.append(key)
        data = OrderedDict()
        # Read the data
        self.read_trace_data(columns)
        for step in steps_to_read:
            for col in columns:
                if col not in data:
                    data[col] = self.get_wave(col, step)
                else:
                    data[col] = np.concatenate((data[col], self.get_wave(col, step)))
            if self._steps is not None and step < len(self._steps):
                for col in step_columns:
                    if col not in data:
                        data[col] = [self._steps[step][col]] * len(data[columns[0]])
                    else:
                        data[col] += [self._steps[step][col]] * len(data[columns[0]])
        return data

    def to_dataframe(self, columns: Union[list, None] = None, step: Union[int, list[int]] = -1, **kwargs):
        """
        Returns a pandas DataFrame with the requested data.

        :param step: Step number to retrieve. If not given, it
        :type step: int
        :param columns: List of traces to use as columns. Default is all traces
        :type columns: list
        :param kwargs: Additional arguments to pass to the pandas.DataFrame constructor
        :type kwargs: ``**dict``
        :return: A pandas DataFrame
        :rtype: pandas.DataFrame
        """
        # cannot type the return values, as pandas is an optional dependency
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("The 'pandas' module is required to use this function.\n"
                              "Use 'pip install pandas' to install it.")
        data = self.export(columns=columns, step=step, **kwargs)
        return pd.DataFrame(data, **kwargs)

    def to_csv(self, filename: Union[str, Path], columns: Union[list[str], None] = None, step: Union[int, list[int]] = -1,
               separator=',', **kwargs):
        """
        Saves the data to a CSV file.

        :param filename: Name of the file to save the data to
        :type filename: str
        :param columns: List of traces to use as columns. Default is all traces
        :type columns: list
        :param step: Step number to retrieve. If not given, it
        :type step: int
        :param separator: separator to use in the CSV file
        :type separator: str
        :param kwargs: Additional arguments to pass to the pandas.DataFrame.to_csv function
        :type kwargs: ``**dict``
        """
        try:
            import pandas as pd
        except ImportError:
            use_pandas = False
        else:
            use_pandas = True

        if use_pandas:
            df = self.to_dataframe(columns=columns, step=step)
            df.to_csv(filename, sep=separator, **kwargs)
        else:
            # Export to CSV using python built-in functions
            data = self.export(columns=columns, step=step)
            with open(filename, 'w') as f:
                f.write(separator.join(data.keys()) + '\n')
                firstcolumn = list(data.keys())[0]
                for i in range(len(data[firstcolumn])):
                    f.write(separator.join([str(data[col][i]) for col in data.keys()]) + '\n')

    def to_excel(self, filename: Union[str, Path], columns: Union[list, None] = None, step: Union[int, list[int]] = -1, **kwargs):
        """
        Saves the data to an Excel file.

        :param filename: Name of the file to save the data to
        :type filename: Union[str, pathlib.Path]
        :param columns: List of traces to use as columns. Default is None, meaning all traces
        :type columns: list, optional
        :param step: Step number to retrieve, defaults to -1
        :type step: Union[int, list[int]], optional
        :param kwargs: Additional arguments to pass to the pandas.DataFrame.to_excel function
        :type kwargs: ``**dict``
        :raises ImportError: when the 'pandas' module is not installed
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("The 'pandas' module is required to use this function.\n"
                              "Use 'pip install pandas' to install it.")
        df = self.to_dataframe(columns=columns, step=step)
        df.to_excel(filename, **kwargs)
