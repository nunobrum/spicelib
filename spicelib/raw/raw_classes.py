#!/usr/bin/env python
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
# Name:        raw_classes.py
# Purpose:     Implements helper classes used in the reading of RAW files.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     19-06-2022
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
Defines base classes for the RAW file data structures.
"""
import numpy as np
from numpy import zeros, complex128, float32, float64
from typing import Union
from abc import ABC, abstractmethod
from pathlib import Path


class DataSet(object):
    """
    This is the base class for storing all traces of a RAW file. Returned by the get_trace() or by the get_axis()
    methods.
    Normally the user doesn't have to be aware of this class. It is only used internally to encapsulate the different
    implementations of the wave population.
    Data can be retrieved directly by using the [] operator.
    If numpy is available, the numpy vector can be retrieved by using the get_wave() method.
    The parameter whattype defines what is the trace representing in the simulation, Voltage, Current a Time or
    Frequency.
    """

    def __init__(self, name, whattype, datalen, numerical_type='real', data: Union[np.ndarray, list] = None):
        """Base Class for both Axis and Trace Classes.
        Defines the common operations between both."""
        self.name = name
        self.whattype = whattype
        self.numerical_type = numerical_type
        self.datalen = datalen
        if data is not None:
            self.data = data
            assert len(self.data) == datalen, "Data length does not match the expected length"
        else:
            if numerical_type == 'double':
                self.data = zeros(datalen, dtype=float64)
            elif numerical_type == 'real':
                self.data = zeros(datalen, dtype=float32)
            elif numerical_type == 'complex':
                self.data = zeros(datalen, dtype=complex128)
            else:
                raise NotImplementedError

    def __str__(self):
        return f"name:'{self.name}'\ntype:'{self.whattype}'\nlen:{len(self.data)}"

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def get_wave(self) -> np.ndarray:
        """
        :return: Internal data array
        :rtype: numpy.array
        """
        return self.data


class Axis(DataSet):
    """This class is used to represent the horizontal axis like on a Transient or DC Sweep Simulation. It derives from
    the DataSet and defines additional methods that are specific for X axis.
    This class is constructed by the get_time_axis() method or by a get_trace(0) command. In RAW files the trace 0 is
    always the X Axis. Ex: time for .TRAN simulations and frequency for the .AC simulations.

    To access data inside this class, the get_wave() should be used, which implements the support for the STEPed data.
    IF Numpy is available, get_wave() will return a numpy array.

    In Transient Analysis and in DC transfer characteristic, LTSpice uses doubles to store the axis values. QSpice
    uses doubles for all variables.
    """

    def __init__(self, name: str, whattype: str, datalen: int, numerical_type: str = 'double',
                 data: Union[np.ndarray, list] = None):
        super().__init__(name, whattype, datalen, numerical_type, data)
        self.step_info = None

    def set_steps(self, step_info: list[dict]):
        self.step_info = step_info
        self.step_offsets = [None for _ in range(len(step_info))]

        # Now going to calculate the point offset for each step
        self.step_offsets[0] = 0
        i = 1
        k = 1
        while i < len(self.data):
            if self.data[i] == self.data[0]:
                self.step_offsets[k] = i
                k += 1
            i += 1

        if k != len(self.step_info):
            raise SpiceReadException("The file a different number of steps than expected.\n" +
                                     "Expecting %d got %d" % (len(self.step_offsets), k))

    def step_offset(self, step: int) -> int:
        """
        In Stepped RAW files, several simulations runs are stored in the same RAW file. This function returns the
        offset within the binary stream where each step starts.

        :param step: Number of the step within the RAW file
        :type step: int
        :return: The offset within the RAW file
        :rtype: int
        """
        if self.step_info is None:
            if step > 0:
                return len(self.data)
            else:
                return 0
        else:
            if step >= len(self.step_offsets):
                return len(self.data)
            else:
                return self.step_offsets[step]

    def get_wave(self, step: int = 0) -> np.ndarray:
        """
        Returns a vector containing the wave values. If numpy is installed, data is returned as a numpy array.
        If not, the wave is returned as a list of floats.

        If stepped data is present in the array, the user should specify which step is to be returned. Failing to do so,
        will return all available steps concatenated together.

        :param step: Optional step in stepped data raw files.
        :type step: int
        :return: The trace values
        :rtype: numpy.array
        """
        if step == 0:
            wave = self.data[:self.step_offset(1)]
        else:
            wave = self.data[self.step_offset(step):self.step_offset(step + 1)]
        if self.name == 'time':  # This is a bug in LTSpice, where the time axis values are sometimes negative
            return np.abs(wave)
        else:
            return wave

    def get_time_axis(self, step: int = 0) -> np.ndarray:
        """
        .. deprecated:: 1.0 Use `get_wave()` instead.

        Returns the time axis raw data. Please note that the time axis may not have a constant time step. LTSpice will
        increase the time-step in simulation phases where there aren't value changes, and decrease time step in
        the parts where more time accuracy is needed.

        :param step: Optional step number if reading a raw file with stepped data.
        :type step: int
        :return: time axis
        :rtype: numpy.array
        """
        assert self.name == 'time', \
            "This function is only applicable to transient analysis, where a bug exists on the time signal"
        return self.get_wave(step)

    def get_point(self, n: int, step: int = 0) -> Union[float, complex]:
        """
        Get a point from the dataset
        
        :param n: position on the vector
        :type n: int
        :param step: step index, defaults to 0
        :type step: int, optional
        :returns: Value of the data point
        :rtype: float, complex
        """
        return self.data[n + self.step_offset(step)]

    def __getitem__(self, item) -> Union[float, complex]:
        """This is only here for compatibility with previous code. """
        assert self.step_info is None, "Indexing should not be used with stepped data. Use get_point or get_wave"
        return self.data.__getitem__(item)

    def get_position(self, t, step: int = 0) -> Union[int, float]:
        """
        Returns the position of a point in the axis. If the point doesn't exist, an interpolation is done between the
        two closest points.
        For example, if the point requested is 1.0001ms and the closest points that exist in the axis are t[100]=1ms and
        t[101]=1.001ms, then the return value will be 100 + (1.0001ms-1ms)/(1.001ms-1ms) = 100.1

        :param t: point in axis to search for
        :type t: float
        :param step: step number
        :type step: int
        :returns: The position of parameter /t/ in the axis
        :rtype: int, float
        """
        if self.name == 'time':
            timex = self.get_time_axis(step)
        else:
            timex = self.get_wave(step)
        for i, x in enumerate(timex):
            if x == t:
                return i
            elif x > t:
                # Needs to interpolate the data
                if i == 0:
                    raise IndexError("Time position is lower than t0")
                frac = (t - timex[i - 1]) / (timex[i] - timex[i - 1])
                return i - 1 + frac

    def get_len(self, step: int = 0) -> int:
        """
        Returns the length of the axis.
        
        :param step: Optional parameter the step index.
        :type step: int
        :return: The number of data points
        :rtype: int
        """
        return self.step_offset(step + 1) - self.step_offset(step)

    def __len__(self):
        if self.step_info is None:
            return len(self.data)
        else:
            return self.get_len()

    def __iter__(self):
        assert self.step_info is None, "Iteration can't be used with stepped data. Use get_wave() method."
        return self.data.__iter__()


class TraceRead(DataSet):
    """This class is used to represent a trace. It derives from DataSet and implements the additional methods to
    support STEPed simulations.
    This class is constructed by the get_trace() command.
    Data can be accessed through the [] and len() operators, or by the get_wave() method.
    If numpy is available the get_wave() method will return a numpy array.
    """

    def __init__(self, name, whattype, datalen, axis, numerical_type='real', data: Union[np.ndarray, list] = None):
        super().__init__(name, whattype, datalen, numerical_type, data)
        self.axis = axis

    def get_point(self, n: int, step: int = 0) -> Union[float, complex]:
        """
        Implementation of the [] operator.

        :param n: item in the array
        :type n: int
        :param step: Optional step number
        :type step: int
        :return: float value of the item
        :rtype: float, complex
        """
        if self.axis is None:
            if n != 0:
                return self.data[n]
            else:
                return self.data[step]  # This is for the case of stepped operation point simulation.
        else:
            return self.data[self.axis.step_offset(step) + n]

    def __getitem__(self, item) -> Union[float, complex]:
        """This is only here for compatibility with previous code. """
        assert self.axis is None or self.axis.step_info is None, \
            "Indexing should not be used with stepped data. Use get_point() method"
        return self.data.__getitem__(item)

    def get_wave(self, step: int = 0) -> np.ndarray:
        """
        Returns the data contained in this object. For stepped simulations an argument must be passed specifying the
        step number. If no steps exist, the argument must be left blank.
        To know whether stepped data exist, the user can use the get_raw_property('Flags') method.

        If numpy is available the get_wave() method will return a numpy array.

        :param step: To be used when stepped data exist on the RAW file.
        :type step: int
        :return: a List or numpy array (if installed) containing the data contained in this object.
        :rtype: numpy.array
        """
        if self.axis is None:
            return super().get_wave()
        else:
            if step == 0:
                return self.data[:self.axis.step_offset(1)]
            else:
                return self.data[self.axis.step_offset(step):self.axis.step_offset(step + 1)]

    def get_point_at(self, t, step: int = 0) -> Union[float, complex]:
        """
        Get a point from the trace at the point specified by the /t/ argument.
        If the point doesn't exist on the axis, the data is interpolated using a linear regression between the two
        adjacent points.
        
        :param t: point in the axis where to find the point.
        :type t: float, float32(numpy) or float64(numpy)
        :param step: step index
        :type step: int
        """
        pos = self.axis.get_position(t, step)
        if isinstance(pos, (float, float32, float64)):
            offset = self.axis.step_offset(step)
            i = int(pos)
            last_item = self.get_len(step) - 1
            if i < last_item:
                f = pos - i
                return self.data[offset + i] + f * (self.data[offset + i + 1] - self.data[offset + i])
            elif pos == last_item:  # This covers the case where a float is given containing the last position
                return self.data[offset + i]
            else:
                raise IndexError(f"The highest index is {last_item}. Received {pos}")
        else:
            return self.get_point(pos, step)

    def get_len(self, step: int = 0) -> int:
        """
        Returns the length of the axis.
        
        :param step: Optional parameter the step index.
        :type step: int
        :return: The number of data points
        :rtype: int
        """
        return self.axis.step_offset(step + 1)

    def __len__(self):
        """
        .. deprecated:: 1.0 This is only here for compatibility with previous code.
        """
        assert self.axis is None or self.axis.step_info is None, \
            "len() should not be used with stepped data. Use get_len() method passing the step index"
        return len(self.data)


class DummyTrace(DataSet):
    """Dummy Trace for bypassing traces while reading"""

    def __init__(self, name, whattype, datalen, numerical_type='real'):
        """Base Class for both Axis and Trace Classes.
        Defines the common operations between both."""
        self.name = name
        self.whattype = whattype
        self.datalen = datalen
        self.numerical_type = numerical_type

    def __str__(self):
        return f"name:'{self.name}'\ntype:'{self.whattype}'\nlen:{self.datalen}"
    
    # dummy, to silence IDE errors
    def get_wave(self, step: int = 0) -> np.ndarray:
        return np.zeros(self.datalen)


class SpiceReadException(Exception):
    """Custom class for exception handling"""
    ...


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
