from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

import numpy as np

from spicelib.raw.raw_classes import Axis, TraceRead

# Constants
MIN_BYTES_IN_FILE = 20

# base class that has the minimum for a plot. Inherited by the PlotData and RawRead classes
class PlotInterface(ABC):

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
    def get_trace(self, trace_ref: Union[str, int]) -> Union[Axis, TraceRead]:
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
    def to_excel(self, filename: Union[str, Path], columns: Union[list, None] = None, step: Union[int, list[int]] = -1,
                 **kwargs):
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


