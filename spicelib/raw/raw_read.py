# coding=utf-8

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        raw_read.py
# Purpose:     Process Spice output files and align data for usage in a spreadsheet
#              tool such as Excel, or Calc.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

"""
This module reads data from an Spice RAW file.
The main class object is the RawRead which is initialized with the filename of the RAW file to be processed.
The object wil read the file and construct a structure of objects which can be used to access the data inside the
RAW file.
To understand why this is done so, in the next section follows a brief explanation of what is contained inside a RAW
file.
In case RAW file contains stepped data detected, i.e. when the .STEP command is used, then it will also try to open the
simulation LOG file and read the stepping information.

RAW File Structure
==================

This section is written to help understand the why the structure of classes is defined as it is. You can gladly skip
this section and get right down to business by seeing the examples section below.

The RAW file starts with a text preamble that contains information about the names of the traces the order they
appear and some extra information.
In the preamble, the lines are always started by one of the following identifiers:

   + Title:          => Contains the path of the source .asc file used to make the simulation preceded by *

   + Date:           => Date when the simulation started

   + Plotname:       => Name of the simulation. Some known Simulation Types are:
                       * AC Analysis
                       * DC transfer characteristic
                       * Operating Point
                       * Transient Analysis
                       * Transfer Function
                       * Noise Spectral Density
                       * Frequency Response Analysis
                       * Noise Spectral Density Curves
                       * Integrated Noise

   + Flags:          => Flags that are used in this plot. The simulation can have any combination of these flags.
                      * "real" -> The traces in the raw file contain real values. As for example on a TRAN simulation.
                      * "complex" -> Traces in the raw file contain complex values. As for example on an AC simulation.
                      * "forward" -> Tells whether the simulation has more than one point. DC transfer
                        characteristic, AC Analysis, Transient Analysis or Noise Spectral Density have the forward flag.
                        Operating Point and Transfer Function don't have this flag activated.
                      * "log" -> The preferred plot view of this data is logarithmic.
                      * "linear" -> The preferred plot view of this data is linear.
                      * "stepped" -> The simulation had .STEP primitives.
                      * "FastAccess" -> Order of the data is changed to speed up access. See Binary section for details.

   + No. Variables:  => number of variables contained in this dataset. See section below for details.

   + No. Points:     => number of points per each variable in

   + Offset:         => when the saving of data started

   + Command:        => Name of the simulator executable generating this file.

   + Backannotation: => Backannotation alerts that occurred during simulation

   + Variables:      => a list of variable, one per line. See section below for details.

   + Binary|Values:  => Start of the trace section, resp. in binary form or ASCII form. See section below for details.
   
Multiple trace sets in one RAW file
-----------------------------------

When a simulation is run with multiple .STEP commands, it is possible to have multiple sets of traces in the same RAW file.
In this case, the RAW file will contain separate sections for each set of traces, each with its own header and data, all tightly concatenated.

Variables List
--------------
The variable list contains the list of measurements saved in the raw file. The order of the variables defines how they
are stored in the binary section. The format is one variable per line, using the following format:

<tab><ordinal number><tab><measurement><tab><type of measurement>

Here is an example:

.. code-block:: text

    0	time	time
    1	V(n001)	   voltage
    2	V(n004)	   voltage
    3	V(n003)	   voltage
    4	V(n006)	   voltage
    5	V(adcc)    voltage
    6	V(n002)	   voltage
    7	V(3v3_m)   voltage
    8	V(n005)	   voltage
    9	V(n007)	   voltage
    10	V(24v_dsp) voltage
    11	I(C3)	   device_current
    12	I(C2)	   device_current
    13	I(C1)	   device_current
    14	I(I1)	   device_current
    15	I(R4)	   device_current
    16	I(R3)	   device_current
    17	I(V2)	   device_current
    18	I(V1)	   device_current
    19	Ix(u1:+)   subckt_current
    20	Ix(u1:-)   subckt_current

Trace Section
--------------
The trace section of .RAW file is where the data is usually written. It is in binary format or in text format.
Spice stores data directly onto the disk during simulation, writing per each time or frequency step the list of
values, as exemplified below for a .TRAN simulation.

     <timestamp 0><trace1 0><trace2 0><trace3 0>...<traceN 0>

     <timestamp 1><trace1 1><trace2 1><trace3 1>...<traceN 1>

     <timestamp 2><trace1 2><trace2 2><trace3 2>...<traceN 2>

     ...

     <timestamp T><trace1 T><trace2 T><trace3 T>...<traceN T>
     
Depending on the type of simulation, and the configuration of the simulator, when using the binary format, the type of data changes.
On TRAN simulations the timestamp is always stored as 8 bytes float (double) and trace values as 4 bytes (single).
On AC simulations the data is stored in complex format, which includes a real part and an imaginary part, each with 8
bytes.
The way we determine the size of the data is dividing the total block size by the number of points, then taking only
the integer part.

Fast Access
-----------

Once a simulation is done, the user can ask the simulator to optimize the data structure in such that variables are stored
contiguously as illustrated below.

     <timestamp 0><timestamp 1>...<timestamp T>

     <trace1 0><trace1 1>...<trace1 T>

     <trace2 0><trace2 1>...<trace2 T>

     <trace3 0><trace3 1>...<trace3 T>

     ...

     <traceN T><traceN T>...<tranceN T>

This can speed up the data reading. Note that this transformation is not done automatically. Transforming data to Fast
Access must be requested by the user. If the transformation is done, it is registered in the Flags: line in the
header. RawReader supports both Normal and Fast Access formats

Classes Defined
===============

The .RAW file is read during the construction (constructor method) of an `RawRead` object. All traces on the RAW
file are uploaded into memory.

The RawRead class then has all the methods that allow the user to access the Axis and Trace Values. If there is
any stepped data (.STEP primitives), the RawRead class will try to load the log information from the same
directory as the raw file in order to obtain the STEP information.

Follows an example of the RawRead class usage. Information on the RawRead methods can be found here.

Examples
========

The example below demonstrates the usage of the RawRead class. It reads a .RAW file and uses the matplotlib
library to plot the results of three traces in two subplots. ::

    import matplotlib.pyplot as plt  # Imports the matplotlib library for plotting the results

    LTR = RawRead("some_random_file.raw")  # Reads the RAW file contents from file

    print(LTR.get_trace_names())  # Prints the contents of the RAW file. The result is a list, and print formats it.
    print(LTR.get_raw_properties())  # Prints all the properties found in the Header section.

    plt.figure()  # Creates the canvas for plotting

    vin = LTR.get_trace('V(in)')  # Gets the trace data. If Numpy is installed, then it comes in numpy array format.
    vout = LTR.get_trace('V(out)') # Gets the second trace.

    steps = LTR.get_steps()  # Gets the step information. Returns a list of step numbers, ex: [0,1,2...]. If no steps
                             # are present on the RAW file, returns only one step : [0] .

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)  # Creates the two subplots. One on top of the other.

    for ax in (ax1, ax2):  # Crates a grid on all the plots.
        ax.grid(True)

    plt.xlim([0.9e-3, 1.2e-3])  # Optionally, limits the X axis to just a subrange.

    x = LTR.get_axis(0)  # Retrieves the time vector that will be used as X axis. Uses STEP 0
    ax1.plot(x, vin.get_wave(0)) # On first plot plots the first STEP (=0) of Vin

    for step in steps:  # On the second plot prints all the STEPS of the Vout
        x = LTR.get_axis(step)  # Retrieves the time vector that will be used as X axis.
        ax2.plot(x, vout.get_wave(step))

    plt.show()  # Creates the matplotlib's interactive window with the plots.

"""

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2022, Fribourg Switzerland"

import os

from collections import OrderedDict
from struct import unpack
from typing import Union
from pathlib import Path
from typing import Protocol
from abc import abstractmethod

from spicelib.log.logfile_data import try_convert_value

from .raw_classes import Axis, TraceRead, DummyTrace, SpiceReadException
from ..utils.detect_encoding import detect_encoding, EncodingDetectError

import numpy as np
from numpy import float32, float64, frombuffer
from ..editor.base_editor import scan_eng
import logging
import re
_logger = logging.getLogger("spicelib.RawRead")

# Constants
MIN_BYTES_IN_FILE = 20

# helper functions


def read_float64(f):
    """
    Reads a 64-bit float value, normally associated with the plot X axis.
    The codification is done as follows:

    =====  === === === ===   === === === ===
    bit#   7   6   5   4     3   2   1   0
    =====  === === === ===   === === === ===
    Byte7  SGM SGE E9  E8    E7  E6  E5  E4
    Byte6  E3  E2  E1  E0    M51 M50 M49 M48
    Byte5  M47 M46 M45 M44   M43 M42 M41 M40
    Byte4  M39 M38 M37 M36   M35 M34 M33 M32
    Byte3  M31 M30 M29 M28   M27 M26 M25 M24
    Byte2  M23 M22 M21 M20   M19 M18 M17 M16
    Byte1  M15 M14 M13 M12   M11 M10 M9  M8
    Byte0  M7  M6  M5  M4    M3  M2  M1  M0
    =====  === === === ===   === === === ===

    Legend:

    SGM - Signal of Mantissa: 0 - Positive 1 - Negative

    SGE - Signal of Exponent: 0 - Positive 1 - Negative

    E[9:0] - Exponent

    M[51:0] - Mantissa.

    :param f: data stream to convert to float value
    :type f: file
    :returns: double precision float
    :rtype: float
    """
    s = f.read(8)
    if len(s) < 8:
        raise SpiceReadException("Invalid RAW file. Not enough data to read a double value.")
    return unpack("d", s)[0]


def read_complex(f):
    """
    Used to convert a 16 byte stream into a complex data point. Usually used for the .AC simulations.
    The encoding is the same as for the set_pointB8() but two values are encoded. First one is the real part and
    the second is the complex part.

    :param f: data stream
    :type f: file
    :return: complex value
    :rtype: complex
    """
    s = f.read(16)
    if len(s) < 16:
        raise SpiceReadException("Invalid RAW file. Not enough data to read a complex value.")
    (re, im) = unpack('dd', s)
    return complex(re, im)


def read_float32(f):
    """
    Reads a 32bit float (single precision) from a stream. This is how most real values are stored in the RAW file.
    This codification uses 4 bytes as follows:

    =====  === === === ===   === === === ===
    bit#   7   6   5   4     3   2   1   0
    =====  === === === ===   === === === ===
    Byte3  SGM SGE E6  E5    E4  E3  E2  E1
    Byte2  E0  M22 M21 M20   M19 M18 M17 M16
    Byte1  M15 M14 M13 M12   M11 M10 M9  M8
    Byte0  M7  M6  M5  M4    M3  M2  M1  M0
    =====  === === === ===   === === === ===

    Legend:

    SGM - Signal of Mantissa: 0 - Positive 1 - Negative

    SGE - Signal of Exponent: 0 - Positive 1 - Negative

    E[6:0] - Exponent

    M[22:0] - Mantissa.

    :param f: data stream to read from
    :type f: file
    :returns: float value
    :rtype: float
    """
    s = f.read(4)
    if len(s) < 4:
        raise SpiceReadException("Invalid RAW file. Not enough data to read a float value.")
    return unpack("f", s)[0]


def consume4bytes(f):
    """Used to advance the file pointer 4 bytes"""
    f.read(4)


def consume8bytes(f):
    """Used to advance the file pointer 8 bytes"""
    f.read(8)


def consume16bytes(f):
    """Used to advance the file pointer 16 bytes"""
    f.read(16)


def namify(spice_ref: str):
    """Translate from V(0,n01) to V__n01__ and I(R1) to I__R1__"""
    if spice_ref.lower() in ('time', 'frequency'):
        return spice_ref
    matchobj = re.match(r'(V|I|P)\((\w+)\)', spice_ref)
    if matchobj:
        return f'{matchobj.group(1)}__{matchobj.group(2)}__'
    else:
        raise NotImplementedError(f'Unrecognized alias type for alias : "{spice_ref}"')


# base class that has the minimum for a plot. Inherited by the PlotData and RawRead classes
class PlotInterface(Protocol):
    
    @property
    @abstractmethod
    def nVariables(self) -> int:
        """Number of variables in the RAW file
        """
        ...

    @property
    @abstractmethod
    def nPoints(self) -> int:
        """Number of points in the RAW file
        """
        ...
    
    @property
    @abstractmethod
    def raw_type(self) -> str:
        """The type of the RAW file, either 'binary:' or 'values:'"""
        ...
    
    @property
    @abstractmethod
    def aliases(self) -> dict[str, str]:
        """QSpice defines aliases for some of the traces that can be computed from other traces.
        """
        ...

    @property
    @abstractmethod
    def backannotations(self) -> list[str]:
        """List to store the backannotations found in the RAW file header
        """
        ...

    @property
    @abstractmethod
    def has_axis(self) -> bool:
        """Indicates if the RAW file has an axis.
        This is True for all RAW file plots except for 'Operating Point', 'Transfer Function', and 'Integrated Noise'.
        """
        ...
    
    @property
    @abstractmethod
    def flags(self) -> list[str]:
        """List of Flags that are used in this plot. See :doc:`../varia/raw_file` for details.
        """
        ...

    @property
    @abstractmethod
    def steps(self) -> Union[list[dict[str, int]], None]:        
        """List of steps in the RAW file, if it exists.
        If the RAW file does not contain stepped data, this will be None.
        If the RAW file contains stepped data, this will be a list of step numbers.
        """
        ...
    
    @abstractmethod
    def get_raw_property(self, property_name=None) -> Union[str, dict[str, str]]:    
        """
        Get a property. By default, it returns all properties defined in the RAW file.

        :param property_name: name of the property to retrieve. If None, all properties are returned.
        :type property_name: str
        :returns: Property object
        :rtype: str
        :raises: ValueError if the property doesn't exist
        """
        ...

    @abstractmethod
    def get_raw_properties(self) -> dict[str, str]:
        """
        Get all raw properties.

        :return: Dictionary of all raw properties
        :rtype: dict[str, str]
        """
        ...
    
    @abstractmethod
    def get_plot_name(self) -> str:
        """Returns the type of the plot read from the RAW file. See :doc:`../varia/raw_file` for details."""
        ...

    @abstractmethod
    def get_trace_names(self) -> list[str]:
        """Returns a list of trace names in the plot."""
        ...
    
    @abstractmethod
    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead, DummyTrace]:
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        :raises IndexError: When a trace is not found
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...
    
    @abstractmethod
    def get_len(self, step: int = 0) -> int:
        """
        Returns the length of the data at the give step index.
        
        :param step: the step index, defaults to 0
        :type step: int, optional
        :return: The number of data points
        :rtype: int
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def to_csv(self, filename: Union[str, Path], columns: Union[list, None] = None, step: Union[int, list[int]] = -1,
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
        ...

    @abstractmethod
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
        ...


class PlotData(PlotInterface):
    """Class for holding plot data.
    This class is used to hold the data of a plot, including the axis and traces.
    
    Do not instantiate this class directly, use the ``RawRead`` class instead."""
    
    def __init__(self, raw_file, raw_filename: Path, traces_to_read: Union[str, list[str], tuple[str, ...]], 
                 plot_nr: int, encoding: str, dialect: Union[str, None], headeronly: bool, verbose: bool):
        """Initializes the PlotData object and reads the RAW file.
        
        :nodoc:
        
        This class is not intended to be documented by Sphinx. See RawRead for the parameters. """
        # Initialize and type the instance variables, for the documentation
        self._raw_filename = raw_filename
        self._plot_nr = plot_nr
        self._verbose = verbose
        self._has_data = False  # Indicates if the plot is recognizable

        self._raw_params: OrderedDict = OrderedDict()  # Dictionary to store the raw parameters
        self._raw_params['Filename'] = raw_filename.as_posix()  # Storing the filename as part of the dictionary
        # TODO: use backannotations to store the backannotations
        self._backannotations = []  # Storing backannotations 
        self._encoding = ""  # Encoding of the RAW file, either 'utf_8' or 'utf_16_le'
        self._raw_type = ""  # Type of the RAW file, either 'Binary:' or 'Values:'
        self._aliases = {}  # QSpice defines aliases for some of the traces that can be computed from other traces.
        self._spice_params = {}  # QSpice stores param values in the .raw file. They may have some usage later for
        self._nPoints = 0  # Number of points in the RAW file
        self._nVariables = 0  # Number of variables in the RAW file
        self._dialect = None  # The dialect of the RAW file, either 'ltspice', 'qspice', 'ngspice' or 'xyce'
        self._traces: list[Union[Axis, TraceRead, DummyTrace]] = []
        self._steps = None
        self._axis = None  # Creating the axis
        self._flags = []
        self._has_axis = True  # Indicates if the RAW file has an axis.

        # TODO: Preparation for lazy reading
        # self._fpos_header = 0  # File position of the header section, used to skip the data when reading the header.
        # self._fpos_data = 0  # File position of the data section, used to skip the header when reading the data.

        plotinfo = f"Plot nr {plot_nr}:"

        # mark the file position of the header section
        # self._fpos_header = raw_file.tell()

        # Check how many bytes are still available in the file
        bytes_remaining = self._get_remaining_bytes(raw_file)
        if self._verbose:
            _logger.debug(f"{plotinfo} {bytes_remaining} bytes remaining in file.")
        if bytes_remaining < 4:
            return  # This is very little, probably just end of file, no need to alert the user.
        if bytes_remaining < MIN_BYTES_IN_FILE:
            _logger.warning(f"{plotinfo} Not enough bytes remaining in file. The plot does not exist or is incomplete.")
            raise SpiceReadException(f"Invalid RAW file. {plotinfo} Not enough bytes remaining in file. The plot does not exist.")
    
        self._encoding = encoding
        if self._encoding in ['utf_16_le', 'utf-16']:
            # Detect the encoding of the file
            sz_enc = 2
        else:
            sz_enc = 1
            
        if self._verbose:
            _logger.debug(f"{plotinfo} Reading the file with encoding: '{self._encoding}'")
        
        header = []
        line = ""
        while True:
            ch = raw_file.read(sz_enc).decode(encoding=self._encoding, errors='replace')
            if len(ch) == 0:
                # End of file reached
                if self._verbose:
                    _logger.warning(f"{plotinfo} End of file reached while reading the header.")
                # will raise exception later
                break
            if ch == '\n':
                # read one line. must remove the \r
                # if self._encoding == 'utf_8':  # no idea why utf_16_le would not need that, but this 'if' was here
                line = line.rstrip('\r')
                header.append(line)
                if line.lower() in ('binary:', 'values:'):
                    self._raw_type = line
                    self._has_data = True  # If we got here, we have a valid RAW file with data.
                    break
                line = ""
            else:
                line += ch

        if not self._has_data:
            raise SpiceReadException(f"Invalid RAW file. {plotinfo} Header is incomplete.")
        
        # computing the aliases.
        for line in header:
            if line.startswith('.'):  # This is either a .param or a .alias
                if line.startswith('.param'):
                    # This is a .param line which format as the following pattern ".param temp=27"
                    _, _, line = line.partition('.param')
                    k, _, v = line.partition('=')
                    self._spice_params[k.strip()] = v.strip()
                elif line.startswith('.alias'):
                    # This is a .param line which format as the following pattern ".alias I(R2) (0.0001mho*V(n01,out))"
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
            raise SpiceReadException(f"Invalid RAW file. {plotinfo} No points or variables found: Points: {self._nPoints}, Variables: {self._nVariables}.")

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
                    _logger.warning(f"{plotinfo} Dialect is ambiguous: '{self._raw_params['Command']}'. Using qspice.")
                autodetected_dialect = 'qspice'
            if 'ngspice' in self._raw_params['Command'].lower():
                # Can only be auto detected from ngspice 44 on, as before there was no "Command:" 
                # binary types: always double for time, complex for AC
                # see if I already saw an autodetected dialect
                if dialect is None and autodetected_dialect is not None:
                    _logger.warning(f"{plotinfo} Dialect is ambiguous: '{self._raw_params['Command']}'. Using ngspice.")
                autodetected_dialect = 'ngspice'
            if 'xyce' in self._raw_params['Command'].lower():
                # Cannot be auto detected yet (at least not on 7.9, where there is no "Command:")
                #  Flags: real (for time) and complex (for frequency)
                #  Binary types: always double for time, complex for AC
                #  and potentially a text (csv) section that follows, that can be ignored.
                # see if I already saw an autodetected dialect
                if dialect is None and autodetected_dialect is not None:
                    _logger.warning(f"{plotinfo} Dialect is ambiguous: '{self._raw_params['Command']}'. Using xyce.")
                autodetected_dialect = 'xyce'
        
        if dialect:
            if autodetected_dialect is not None:
                if dialect != autodetected_dialect:
                    _logger.warning(f"{plotinfo} Dialect specified as {dialect}, but the file seems to be from {autodetected_dialect}. Trying to read it anyway.")
        else:
            # no dialect given. Take the autodetected version
            dialect = autodetected_dialect

        # Do I have something?
        if not dialect:
            raise SpiceReadException(f"Invalid RAW file. {plotinfo} file dialect is not specified and could not be auto detected.")

        # and tell the outside world
        self._dialect = dialect
        
        # set the specifics per dialect
        always_double = dialect != 'ltspice'  # qspice, ngspice and xyce use doubles for everything outside of AC files
        frequency_double = dialect == 'qspice'  # qspice uses double also for frequency for AC files
        
        self._traces = []
        self._steps = None
        self._axis = None  # Creating the axis
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
        i = header.index('Variables:')
        ivar = 0
        for line in header[i + 1:-1]:  # Parse the variable names
            line_elmts = line.lstrip().split('\t')
            if len(line_elmts) < 3:
                raise SpiceReadException(f"Invalid RAW file. {plotinfo} Invalid line in the Variables section: {line}")
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
                self._axis = Axis(name, var_type, self._nPoints, axis_numerical_type)
                trace = self._axis
            elif (traces_to_read == "*") or (name in traces_to_read):
                if self._has_axis:  # Reads data
                    trace = TraceRead(name, var_type, self._nPoints, self._axis, numerical_type)
                else:
                    # If an Operation Point or Transfer Function, only one point per step
                    trace = TraceRead(name, var_type, self._nPoints, None, numerical_type)
            else:
                trace = DummyTrace(name, var_type, self._nPoints, numerical_type)

            self._traces.append(trace)
            ivar += 1

        if self._verbose:
            nr_traces_to_read = len([trace for trace in self._traces if not isinstance(trace, DummyTrace)])
            _logger.info(f"{plotinfo} Plot is of type '{self.get_plot_name()}', contains {ivar} traces with {self._nPoints} points, reading {nr_traces_to_read} traces.")

        # Now, we have the header read, and the traces created.
        # We can now read the data section.

        # mark the file position of the start of the data section
        # self._fpos_data = raw_file.tell()

        if self._raw_type.lower() == "binary:":
            # Will start the reading of binary values
            
            if "fastaccess" in self._raw_params["Flags"].lower():
                if self._verbose:
                    _logger.debug(f"{plotinfo} Binary RAW file with Fast access")
                # Fast access means that the traces are grouped together.
                for i, var in enumerate(self._traces):
                    datasize = 8
                    dtype = float64
                    if var.numerical_type == 'double':
                        datasize = 8
                        dtype = float64
                    elif var.numerical_type == 'complex':
                        datasize = 16
                        dtype = complex
                    elif var.numerical_type == 'real':  # data size is only 4 bytes
                        datasize = 4
                        dtype = float32
                    else:
                        raise SpiceReadException(f"Invalid RAW file. {plotinfo} Invalid data type {var.numerical_type} for trace {var.name}")
                    
                    if headeronly:
                        # If headeronly is set, we do not read the data section.
                        if self._verbose:
                            _logger.debug(f"{plotinfo} Skipping data section as headeronly is set.")
                        target_pos = raw_file.tell() + (datasize * self._nPoints)
                        newpos = raw_file.seek(target_pos, os.SEEK_SET)
                        if newpos != target_pos:
                            raise SpiceReadException(f"Invalid RAW file. {plotinfo} Could not seek to the end of the data section. File is incomplete.")
                    else:
                        s = raw_file.read(self._nPoints * datasize)
                        if len(s) == 0:
                            # End of file reached
                            if self._verbose:
                                _logger.warning(f"{plotinfo} End of file reached while reading the data for trace {var.name}.")
                            raise SpiceReadException(f"Invalid RAW file. {plotinfo} End of file reached while reading the data for trace {var.name}.")
                            
                        if not isinstance(var, DummyTrace):
                            var.data = frombuffer(s, dtype=dtype)

            else:
                # This is the default save after a simulation where the traces are scattered
                if self._verbose:
                    _logger.debug(f"{plotinfo} Binary RAW file with Normal access")
                    
                scan_functions = []
                calc_block_size = 0
                for trace in self._traces:
                    if trace.numerical_type == 'double':
                        calc_block_size += 8
                        if isinstance(trace, DummyTrace):
                            fun = consume8bytes
                        else:
                            fun = read_float64
                    elif trace.numerical_type == 'complex':
                        calc_block_size += 16
                        if isinstance(trace, DummyTrace):
                            fun = consume16bytes
                        else:
                            fun = read_complex
                    elif trace.numerical_type == 'real':  # data size is only 4 bytes
                        calc_block_size += 4
                        if isinstance(trace, DummyTrace):
                            fun = consume4bytes
                        else:
                            fun = read_float32
                    else:
                        raise SpiceReadException(
                            f"Invalid RAW file. {plotinfo} Invalid data type {trace.numerical_type} for trace {trace.name}")
                    scan_functions.append(fun)
                    
                # read the data
                if headeronly:
                    # If headeronly is set, we do not read the data section.
                    if self._verbose:
                        _logger.debug(f"{plotinfo} Skipping data section as headeronly is set.")

                    target_pos = raw_file.tell() + calc_block_size * self._nPoints
                    newpos = raw_file.seek(target_pos, os.SEEK_SET)
                    if newpos != target_pos:
                        raise SpiceReadException(f"Invalid RAW file. {plotinfo} Could not seek to the end of the data section. File is incomplete.")
                else:
                    for point in range(self._nPoints):
                        for i, var in enumerate(self._traces):
                            value = scan_functions[i](raw_file)
                            if value is not None and not isinstance(var, DummyTrace):
                                var.data[point] = value

        elif self._raw_type.lower() == "values:":
            if self._verbose:
                _logger.debug(f"{plotinfo} ASCII RAW File")
            # Will start the reading of ASCII Values
            for point in range(self._nPoints):
                line_nr = 0
                while line_nr < len(self._traces):
                    line = raw_file.readline().decode(encoding=self._encoding, errors='ignore')
                    if len(line) == 0:
                        raise SpiceReadException(f"Invalid RAW file. {plotinfo} Invalid data: end of file encountered too early")
                    if len(line.strip()) == 0:
                        continue  # skip empty lines
                    if line_nr == 0:
                        s_point = line.split("\t", 1)[0]

                        if point != int(s_point):
                            raise SpiceReadException(f"Invalid RAW file. {plotinfo}Invalid data: point is not in sequence ({point} != {int(s_point)})")
                        value = line[len(s_point):-1]
                    else:
                        value = line[:-1]
                    
                    var = self._traces[line_nr]
                    if not isinstance(var, DummyTrace):
                        if var.numerical_type == 'complex':
                            v = value.split(',')
                            if len(v) != 2:
                                raise SpiceReadException(f"Invalid RAW file. {plotinfo}Invalid data for trace {var.name}: {value} is not a complex value")
                            var.data[point] = complex(float(v[0]), float(v[1]))
                        else:
                            var.data[point] = float(value)
                    line_nr += 1
        else:
            raise SpiceReadException(f"Invalid RAW file. {plotinfo} Unsupported RAW type \"{self._raw_type}\"")

        # Setting the properties in the proper format
        self._raw_params["Variables"] = [var.name for var in self._traces]
        # Now Purging Dummy Traces
        i = 0
        while i < len(self._traces):
            if isinstance(self._traces[i], DummyTrace):
                del self._traces[i]
            else:
                i += 1

        # Finally, Check for Step Information
        if "stepped" in self._raw_params["Flags"].lower():
            if self._verbose:
                _logger.debug(f"{plotinfo} RAW file has stepped data.")
            if headeronly:
                if self._verbose:
                    _logger.debug(f"{plotinfo} Skipping step information as headeronly is set.")
                return
            try:
                self._load_step_information(raw_filename, plotinfo)
            except SpiceReadException as err:
                _logger.warning(f"{plotinfo} {str(err)}\nError in auto-detecting steps in '{raw_filename}'")
                if self._has_axis:
                    number_of_steps = 0
                    if self._axis is not None:
                        for v in self._axis.data:
                            if v == self._axis.data[0]:
                                number_of_steps += 1
                else:
                    number_of_steps = self._nPoints
                self._steps = [{'run': i + 1} for i in range(number_of_steps)]

            if self._steps is not None:
                if self._has_axis:
                    # Individual access to the Trace Classes, this information is stored in the Axis
                    # which is always in position 0
                    self._traces[0]._set_steps(self._steps)
        
    def _get_remaining_bytes(self, raw_file) -> int:
        current_pos = raw_file.tell()
        raw_file.seek(0, os.SEEK_END)
        bytes_remaining = raw_file.tell() - current_pos
        raw_file.seek(current_pos)
        return bytes_remaining
                    
    @property
    def has_data(self) -> bool:
        """Indicates if the plot has data."""
        return self._has_data
    
    @property
    def dialect(self) -> Union[str, None]:
        """The dialect of the RAW file, either 'ltspice', 'qspice', 'ngspice' or 'xyce'
        """
        return self._dialect
    
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
        return [trace.name for trace in self._traces] + list(self._aliases.keys())

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
        # converting V(ref1) to V__ref1__ and I(ref1) to I__ref1__
        formula = re.sub(r'(V|I|P)\((\w+)\)', r'\1__\2__', formula)

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
        local_vars.update({namify(trace.name): trace.data for trace in self._traces})
        try:
            trace.data = eval(formula, local_vars)
        except Exception as err:
            raise RuntimeError(f'Error computing alias "{alias}" with formula "{formula}"') from err
        return trace

    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead, DummyTrace]:
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        :raises IndexError: When a trace is not found
        """
        if isinstance(trace_ref, str):
            for trace in self._traces:
                if trace_ref.casefold() == trace.name.casefold():  # The trace names are case-insensitive
                    # assert isinstance(trace, DataSet)
                    return trace
            for alias in self._aliases:
                if trace_ref.casefold() == alias.casefold():
                    return self._compute_alias(alias)
            raise IndexError(f"{self} doesn't contain trace \"{trace_ref}\"\n"
                             f"Valid traces are {[trc.name for trc in self._traces]}")
        else:
            return self._traces[trace_ref]

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
        elif isinstance(trace, DummyTrace):
            return np.full(self.get_len(step), np.nan, dtype=float)
        else:
            raise IndexError(f"{self} doesn't contain trace \"{trace_ref}\"\n"
                             f"Valid traces are {[trc.name for trc in self._traces]}")

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
                             f"Valid traces are {[trc.name for trc in self._traces]}")

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

    def _load_step_information(self, filename: Path, plotinfo: str):
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
                    _logger.debug(f"{plotinfo} Found step {step} with stepset {stepset}.")

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
        # Create the headers with the column names and empty lists
        for col in columns:
            data[col] = []
        for col in step_columns:
            data[col] = []
        # Read the data
        for step in steps_to_read:
            for col in columns:
                data[col] += list(self.get_wave(col, step))
            if self._steps is not None and step < len(self._steps):
                for col in step_columns:
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
    

class RawRead(PlotInterface):
    """Class for reading Spice wave Files. It can read all types of Files, and can handle multiple plots in 1 file.
    If stepped data is detected, it will also try to read the corresponding LOG file so to retrieve the stepped data.

    :param raw_filename: The file containing the RAW data to be read
    :type raw_filename: str or pathlib.Path
    :param traces_to_read:
        A string or a list containing the list of traces to be read. If None is provided, only the header is read and
        all trace data is discarded. If a '*' wildcard is given or no parameter at all then all traces are read.
    :type traces_to_read: str, list or tuple
    :param dialect: The simulator used. 
        Please select from ["ltspice","qspice","ngspice","xyce"]. If not specified, dialect will be auto detected. 
        This is likely only needed for older versions of ngspice and xyce. ltspice and qspice can reliably be auto detected.
    :type dialect: str | None
    :param headeronly:
        Used to only load the header information and skip the trace data entirely.
        This will only provide a speed advantage for binary RAW files.
        Defaults to False. 
    :type headeronly: bool
    :param verbose:
        If True, then the class will log debug information. Defaults to True.
    :type verbose: bool
    :param force_reading_all:
        If True, then the entire file content will be checked for validity. 
        If False, then only the first plot needs to be valid, and others will be read until an error happens.
        Defaults to False, as some simulators (xyce) tend to write additional data to the raw file.
    :type force_reading_all: bool
    :raises SpiceReadException: in case of a syntax error in the RAW file, or if the encoding is not recognized. 
    """
    # header_lines = (
    #     "Title",
    #     "Date",
    #     "Plotname",
    #     "Output",
    #     "Flags",
    #     "No. Variables",
    #     "No. Points",
    #     "Offset",
    #     "Command",
    #     "Variables",
    #     "Backannotation"
    # )

    # ACCEPTED_PLOTNAMES = (
    #     'AC Analysis',
    #     'DC transfer characteristic',
    #     'Operating Point',
    #     'Transient Analysis',
    #     'Transfer Function',
    #     'Noise Spectral Density',
    #     'Frequency Response Analysis',
    #     'Noise Spectral Density Curves',
    #     'Integrated Noise'
    # )

    def __init__(self, 
                 raw_filename: Union[str, Path], 
                 traces_to_read: Union[str, list[str], tuple[str, ...]] = '*',
                 dialect: Union[str, None] = None, 
                 headeronly: bool = False, 
                 verbose: bool = True,
                 force_reading_all: bool = False):
        """Initializes the RawRead object and reads the RAW file."""
        
        # Initialize and type the instance variables, for the documentation
        self._encoding: str = ""
        self._dialect: Union[str, None] = None
        self._plots: list[PlotData] = []
                
        # ########## The code starts here
        
        # Validate input parameters
        if isinstance(raw_filename, str):
            raw_filename = Path(raw_filename)
            
        if traces_to_read is not None:
            assert isinstance(traces_to_read, (str, list, tuple)), "traces_to_read must be a string, a list or None"
                        
        # clean up given dialect
        if dialect is not None:
            if len(dialect) == 0:
                dialect = None
            else:
                dialect = dialect.lower()
                # given info is correct?
                if dialect not in ('ltspice', 'qspice', 'ngspice', 'xyce'):
                    raise ValueError(f"Invalid RAW file dialect: '{dialect}', must be one of 'ltspice', 'qspice', 'ngspice', 'xyce'.")
        self._dialect = dialect
        
        # detect encoding
        self._encoding = self._detect_encoding(raw_filename)
        if verbose:
            _logger.debug(f"Detected encoding: {self._encoding} for file {raw_filename}")
                
        raw_file = open(raw_filename, "rb")
        
        have_more_data = True
        plot_nr = 1
            
        # read the contents of the file, one plot at a time
        try:
            while have_more_data:
                if plot_nr == 1 or force_reading_all:
                    plot = PlotData(raw_file, raw_filename, traces_to_read, plot_nr, self._encoding, self._dialect, headeronly, verbose)
                else:
                    try:
                        plot = PlotData(raw_file, raw_filename, traces_to_read, plot_nr, self._encoding, self._dialect, headeronly, verbose)
                    except Exception as e:
                        if verbose:
                            _logger.warning(f"Cannot read plot {plot_nr} from {raw_filename}: {e}, stopping reading further plots.")
                        break
                if self._dialect is None:
                    self._dialect = plot.dialect
                if plot.has_data:
                    self._plots.append(plot)
                    plot_nr += 1
                else:
                    have_more_data = False
        finally:
            raw_file.close()
            
    def _detect_encoding(self, raw_filename) -> str:
        """Detects the encoding of the RAW file.
        
        :param raw_file: The file object to read from
        :type raw_file: pathlib.Path
        :return: The encoding of the RAW file
        :rtype: str
        :raises EncodingDetectError: if the encoding cannot be detected
        """
        # I cannot use detectencoding() here, as that only works on real text files. 
        # This may be a partially binary file, where that function breaks.
        # TODO: you might need to take care of the BOM (Byte Order Mark) in the file.
        with open(raw_filename, "rb") as raw_file:
            raw_line = raw_file.read(6)
            if len(raw_line) < 6:
                raise SpiceReadException("Invalid RAW file. File is too short to determine encoding.")
            line = raw_line.decode(encoding='utf_8')
            if line == 'Title:' or line == '\nTitle':
                return 'utf_8'
            else:
                line = raw_line.decode(encoding='utf_16_le')
                if line == 'Tit' or line == '\nTi':
                    return 'utf_16_le'

        raise SpiceReadException("Invalid RAW file. Unrecognized encoding.")  

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
    def plots(self) -> list[PlotData]:
        """List of plots in the RAW file. Each plot is an instance of a class that inherits from PlotData.
        Note that all properties and methods of plots[0] are also available directly in the RawRead class.
        """
        return self._plots

    @property
    def nVariables(self) -> int:
        """Number of variables in the RAW file
        """
        if len(self._plots) == 0:
            return 0
        return self._plots[0].nVariables

    @property
    def nPoints(self) -> int:
        """Number of points in the RAW file
        """
        if len(self._plots) == 0:
            return 0
        return self._plots[0].nPoints

    @property
    def raw_type(self) -> str:
        """The type of the RAW file, either 'binary:' or 'values:'"""
        if len(self._plots) == 0:
            return ""
        return self._plots[0].raw_type 
    
    @property
    def aliases(self) -> dict[str, str]:
        """QSpice defines aliases for some of the traces that can be computed from other traces.
        """
        if len(self._plots) == 0:
            return {}
        return self._plots[0].aliases

    @property
    def backannotations(self) -> list[str]:
        """List to store the backannotations found in the RAW file header
        """
        if len(self._plots) == 0:
            return []
        return self._plots[0].backannotations

    @property
    def has_axis(self) -> bool:
        """Indicates if the RAW file has an axis.
        This is True for all RAW file plots except for 'Operating Point', 'Transfer Function', and 'Integrated Noise'.
        """
        if len(self._plots) == 0:
            return False
        return self._plots[0].has_axis        
    
    @property
    def axis(self) -> Union[Axis, None]:
        """
        .. deprecated:: 1.4.5 Use `get_axis()` method instead.
        
        The axis of the RAW file, if it exists.
        """
        if len(self._plots) == 0:
            return None
        return self._plots[0].axis

    @property
    def raw_params(self) -> OrderedDict:
        """
        .. deprecated:: 1.4.5 Use `get_raw_properties()` or `get_raw_property()` method instead.
        
        Dictionary to store the parameters found in the RAW file header.
        The keys are the parameter names, and the values are the parameter values.
        """
        if len(self._plots) == 0:
            return OrderedDict()
        return self._plots[0].raw_params
    
    @property
    def flags(self) -> list[str]:
        """List of Flags that are used in this plot. See :doc:`../varia/raw_file` for details.
        """
        if len(self._plots) == 0:
            return []
        return self._plots[0].flags
    
    @property
    def steps(self) -> Union[list[dict[str, int]], None]:
        """List of steps in the RAW file, if it exists.
        If the RAW file does not contain stepped data, this will be None.
        If the RAW file contains stepped data, this will be a list of step numbers.
        """
        if len(self._plots) == 0:
            return None
        return self._plots[0].steps
            
    def get_raw_property(self, property_name=None) -> Union[str, dict[str, str]]:
        """
        Get a property. By default, it returns all properties defined in the RAW file.

        :param property_name: name of the property to retrieve. If None, all properties are returned.
        :type property_name: str
        :returns: Property object
        :rtype: str
        :raises: ValueError if the property doesn't exist
        """
        if len(self._plots) == 0:
            return ""
        return self._plots[0].get_raw_property(property_name)

    def get_raw_properties(self) -> dict[str, str]:
        """
        Get all raw properties.

        :return: Dictionary of all raw properties
        :rtype: dict[str, str]
        """
        if len(self._plots) == 0:
            return {}
        return self._plots[0].get_raw_properties()

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
        if len(self._plots) == 0:
            return ""
        return self._plots[0].get_plot_name()
        
    def get_plot_names(self) -> list[str]:
        """
        Returns a list of plot names in the RAW file.

        :return: List of plot names
        :rtype: list[str]
        """
        return [plot.get_plot_name() for plot in self._plots]

    def get_nr_plots(self) -> int:
        """
        Returns the number of plots in the RAW file.

        :return: Number of plots
        :rtype: int
        """
        return len(self._plots)

    def get_trace_names(self) -> list[str]:
        """
        Returns a list of exiting trace names of the RAW file.

        :return: trace names
        :rtype: list[str]
        """
        if len(self._plots) == 0:
            return []
        return self._plots[0].get_trace_names()

    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead, DummyTrace]:
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        :raises IndexError: When a trace is not found
        """
        if len(self._plots) == 0:
            return DummyTrace("No plots found in the RAW file.", "dummy", 0)
        return self._plots[0].get_trace(trace_ref)

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
        if len(self._plots) == 0:
            return np.ndarray([])
        return self._plots[0].get_wave(trace_ref, step)

    def get_time_axis(self, step: int = 0) -> np.ndarray:
        """
        .. deprecated:: 1.0 Use `get_axis()` method instead.

        This function is equivalent to get_trace('time').get_time_axis(step) instruction.
        It's workaround on a LTSpice issue when using 2nd Order compression, where some values on
        the time trace have a negative value."""
        if len(self._plots) == 0:
            return np.ndarray([])
        return self._plots[0].get_time_axis(step)

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
        if len(self._plots) == 0:
            return np.ndarray([])
        return self._plots[0].get_axis(step)

    def get_len(self, step: int = 0) -> int:
        """
        Returns the length of the data at the give step index.
        
        :param step: the step index, defaults to 0
        :type step: int, optional
        :return: The number of data points
        :rtype: int
        """
        if len(self._plots) == 0:
            return 0
        return self._plots[0].get_len(step)

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
        if len(self._plots) == 0:
            return [0]
        return self._plots[0].get_steps(**kwargs)

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
        if len(self._plots) == 0:
            return OrderedDict()  # Return an empty OrderedDict if no plots are found
        return self._plots[0].export(columns=columns, step=step, **kwargs)

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
        if len(self._plots) == 0:
            return None
        return self._plots[0].to_dataframe(columns=columns, step=step, **kwargs)

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
        if len(self._plots) == 0:
            return
        return self._plots[0].to_csv(filename=filename, columns=columns, step=step, separator=separator, **kwargs)

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
        if len(self._plots) == 0:
            return
        return self._plots[0].to_excel(filename=filename, columns=columns, step=step, **kwargs)
