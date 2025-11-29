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
# Purpose:     Reads Spice simulator data files. Ex: .raw or .qraw
#              In regards to the RawRead class which always read the full extend of the RAW file into memory
#              this class only reads the raw file headers and gathers information for reading only the requested
#              information.
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

from collections import OrderedDict
from typing import Union
from pathlib import Path

from .plot_data import PlotData, get_remaining_bytes
from .raw_classes import Axis, TraceRead, SpiceReadException
from .plot_interface import PlotInterface, MIN_BYTES_IN_FILE

import numpy as np
import logging

_logger = logging.getLogger("spicelib.RawRead")


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

    :param verbose:
        If True, then the class will log debug information. Defaults to True.
    :type verbose: bool

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
                 traces_to_read: Union[None, str, list[str], tuple[str, ...]] = None,
                 dialect: Union[str, None] = None,
                 verbose: bool = True):
        """Initializes the RawRead object and reads the RAW file."""

        # Initialize and type the instance variables, for the documentation
        self._plots: list[PlotData] = []

        # Validate input parameters
        if isinstance(raw_filename, str):
            raw_filename = Path(raw_filename)

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
        plot_nr = 1
        # read the contents of the file, one plot at a time
        with open(raw_filename, "rb") as raw_file:
            while get_remaining_bytes(raw_file) > MIN_BYTES_IN_FILE:
                plot = PlotData(raw_file, raw_filename, plot_nr, self.encoding, self._dialect, verbose)
                if self._dialect is None:
                    self._dialect = plot.dialect
                if plot.has_data:
                    self._plots.append(plot)
                    plot_nr += 1

        if traces_to_read is None:
            # No traces to read, just the header
            return
        # Read the trace data, if requested
        for plot in self._plots:
            # if traces_to_read is '*', read all traces
            if isinstance(traces_to_read, str):
                if traces_to_read == '*':
                    traces_to_read = self.get_trace_names()  # * means all traces
                else:
                    traces_to_read = [name.strip() for name in traces_to_read.split(',')]
            elif not isinstance(traces_to_read, (list, tuple)):
                raise SpiceReadException("Invalid traces_to_read parameter. Must be a string, list or tuple.")

            plot.read_trace_data(traces_to_read)

    @property
    def dialect(self) -> Union[str, None]:
        """The dialect of the RAW file, either 'ltspice', 'qspice', 'ngspice' or 'xyce'
        """
        return self._dialect

    @property
    def encoding(self) -> str:
        """The encoding of the RAW file is either 'utf_8' or 'utf_16_le'. It is automatically detected when reading
        the file. If the file was not read yet, an empty string is returned.
        If the RAW file contains multiple plots, the encoding of the first plot is returned.
        """
        return self._plots[0].encoding if len(self._plots) > 0 else ""

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

    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead]:
        """
        Retrieves the trace with the requested name (trace_ref).

        :param trace_ref: Name of the trace or the index of the trace
        :type trace_ref: str or int
        :return: An object containing the requested trace
        :rtype: DataSet subclass
        :raises IndexError: When a trace is not found
        """
        if len(self._plots) == 0:
            raise SpiceReadException("No plots found in the RAW file.")
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
            return {}  # Return an empty dictionary if no plots are found
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
            raise SpiceReadException("No plots found in the RAW file.")
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
            raise SpiceReadException("No plots found in the RAW file.")
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
            raise SpiceReadException("No plots found in the RAW file.")
        return self._plots[0].to_excel(filename=filename, columns=columns, step=step, **kwargs)
