#!/usr/bin/env python
# coding=utf-8
from __future__ import annotations

# -------------------------------------------------------------------------------
# Name:        logfile_data.py
# Purpose:     Store data related to log files. This is a superclass of LTSpiceLogReader
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import re
from typing import Union, Iterable, List
from collections import OrderedDict
import math
import logging

_logger = logging.getLogger("spicelib.LTSteps")


class LTComplex(complex):
    """
    Class to represent complex numbers as exported by LTSpice
    """
    complex_match = re.compile(r"\((?P<mag>.*?)(?P<dB>dB)?,(?P<ph>.*?)(?P<degrees>°)?\)")

    def __new__(self, strvalue):
        match = self.complex_match.match(strvalue)
        if match:
            mag = float(match.group('mag'))
            ph = float(match.group('ph'))
            if match.group('degrees') is None:
                # This is the cartesian format
                return super().__new__(self, mag, ph)
            else:
                if match.group('dB') is not None:
                    # This is the polar format
                    mag = 10 ** (mag / 20)
                return super().__new__(self, mag * math.cos(math.pi * ph / 180), mag * math.sin(math.pi * ph / 180))
        else:
            raise ValueError("Invalid complex value format")

    def __init__(self, strvalue):
        self.strvalue = strvalue

    def __str__(self):
        return self.strvalue

    @property
    def mag(self):
        """Returns the magnitude of the complex number"""
        return abs(self)

    @property
    def ph(self):
        """Returns the phase of the complex number in degrees"""
        return math.atan2(self.imag, self.real) * 180 / math.pi

    def mag_db(self):
        """Returns the magnitude of the complex number in dBV"""
        return 20 * math.log10(self.mag)

    def ph_rad(self):
        return math.atan2(self.imag, self.real)

    @property
    def unit(self):
        _unit = None
        match = self.complex_match.match(self.strvalue)
        if match:
            _unit = match.group('dB')
        return _unit


def try_convert_value(value: Union[str, int, float, list]) -> Union[int, float, str, list, LTComplex]:
    """
    Tries to convert the string into an integer and if it fails, tries to convert to a float, if it fails, then returns the
    value as string.

    :param value: value to convert
    :type value: str, int or float
    :return: converted value, if applicable
    :rtype: int, float, str
    """
    if isinstance(value, (int, float)):
        return value
    elif isinstance(value, list):
        return [try_convert_value(v) for v in value]
    elif isinstance(value, bytes):
        value = value.decode('utf-8')
    try:
        ans = int(value)
    except ValueError:
        try:
            ans = float(value)
        except ValueError:
            try:
                ans = LTComplex(value)
            except ValueError:
                ans = value.strip()  # Removes the leading trailing spaces
    return ans


def split_line_into_values(line: str) -> List[Union[int, float, str]]:
    """
    Splits a line into values. The values are separated by tabs or spaces. If a value starts with ( and ends with ),
    then it is considered a complex value, and it is returned as a single value. If converting values within () fails,
    then the value is returned as a tuple with the values inside the ().
    """
    parenthesis = []
    i = 0
    value_start = 0
    values = []
    for i, c in enumerate(line):
        if c == '(':  # By checking the parenthesis first, we can support nested parenthesis
            parenthesis.insert(0, ')')
        elif c == '[':
            parenthesis.insert(0, ']')
        elif c == '{':
            parenthesis.insert(0, '}')
        elif len(parenthesis) > 0:
            if c == parenthesis[0]:
                parenthesis.pop(0)
                if len(parenthesis) == 0:
                    value_list = split_line_into_values(line[value_start+1:i])  # Excludes the parenthesis
                    values.append(value_list)
                    value_start = i + 1
        elif c in (' ', '\t', '\r', '\n'):
            if value_start < i:
                values.append(try_convert_value(line[value_start:i]))
            value_start = i + 1
        elif c in (',', ';'):
            if value_start < i:
                values.append(try_convert_value(line[value_start:i]))
            else:
                values.append(None)
            value_start = i + 1
    if value_start < i + 1:
        values.append(try_convert_value(line[value_start:i + 1]))
    parenthesis_balanced = len(parenthesis) == 0
    if not parenthesis_balanced:
        raise ValueError("Parenthesis are not balanced")
    return values


class LogfileData:
    """
    This is a subclass of LTSpiceLogReader that is used to analyse the log file of a simulation.
    The super class constructor is bypassed and only their attributes are initialized
    """

    def __init__(self, step_set: dict = None, dataset: dict = None):
        if step_set is None:
            self.stepset = {}
        else:
            self.stepset = step_set.copy()  # A copy is done since the dictionary is a mutable object.
            # Changes in step_set would be propagated to object on the call

        if dataset is None:
            self.dataset = OrderedDict()  # Dictionary in which the order of the keys is kept
        else:
            self.dataset = dataset.copy()  # A copy is done since the dictionary is a mutable object.

        self.step_count = len(self.stepset)
        self.measure_count = len(self.dataset)

    def __getitem__(self, key):
        """
        __getitem__ implements
        :key: step or measurement name. This is case insensitive.
        :return: step or measurement set
        :rtype: List[float]
        """
        if isinstance(key, slice):
            raise NotImplementedError("Slicing in not allowed in this class")
        key = key.lower()
        if key in self.stepset:
            return self.stepset[key]
        if key in self.dataset:
            return self.dataset[key]  # This will raise an Index Error if not found here.
        raise IndexError("'%s' is not a valid step variable or measurement name" % key)

    def has_steps(self):
        """
        Returns true if the simulation has steps
        :return: True if the simulation has steps
        :rtype: bool
        """
        return self.step_count > 0

    def steps_with_parameter_equal_to(self, param: str, value: Union[str, int, float]) -> List[int]:
        """
        Returns the steps that contain a given condition.

        :param param: parameter identifier on a stepped simulation. This is case insensitive.
        :type param: str
        :param value:
        :type value:
        :return: List of positions that respect the condition of equality with parameter value
        :rtype: List[int]
        """
        param = param.lower()
        if param in self.stepset:
            condition_set = self.stepset[param]
        elif param in self.dataset:
            condition_set = self.dataset[param]
        else:
            raise IndexError("'%s' is not a valid step variable or measurement name" % param)
        # tries to convert the value to integer or float, for consistency with data loading implementation
        v = try_convert_value(value)
        # returns the positions where there is match
        return [i for i, a in enumerate(condition_set) if a == v]

    def steps_with_conditions(self, **conditions) -> List[int]:
        """
        Returns the steps that respect one or more equality conditions

        :key conditions: parameters within the Spice simulation. Values are the matches to be found.
        :type conditions: dict
        :return: List of steps that respect all the given conditions
        :rtype: List[int]
        """
        current_set = None
        for param, value in conditions.items():
            condition_set = self.steps_with_parameter_equal_to(param, value)
            if current_set is None:
                # initialises the list
                current_set = condition_set
            else:
                # makes the intersection between the lists
                current_set = [v for v in current_set if v in condition_set]
        return current_set

    def get_step_vars(self) -> List[str]:
        """
        Returns the stepped variable names on the log file.
        :return: List of step variables.
        :rtype: list of str
        """
        return list(self.stepset.keys())

    def get_measure_names(self) -> List[str]:
        """
        Returns the names of the measurements read from the log file.
        :return: List of measurement names.
        :rtype: list of str
        """
        return list(self.dataset.keys())

    def get_measure_value(self, measure: str, step: int | slice = None, **kwargs) -> float | int | str | LTComplex:
        """
        Returns a measure value on a given step.

        :param measure: name of the measurement to get. This is case insensitive.
        :type measure: str
        :param step: optional step number or slice if the simulation has no steps.
        :type step: int or slice
        :param kwargs: additional arguments that can be translated into step conditions
        :return: measurement value
        :rtype: int, float, Complex or str
        """
        measure = measure.lower()
        if step is None:
            if kwargs:
                step = self.steps_with_conditions(**kwargs)
                if len(step) == 1:
                    step = step[0]
                    return self.dataset[measure][step]
                else:
                    raise IndexError("Not sufficient conditions to identify a single step")
            elif len(self.dataset[measure]) == 1:
                return self.dataset[measure][0]
            elif len(self.dataset[measure]) == 0:
                _logger.error(f'No measurements found for measure "{measure}"')
            else:
                raise IndexError("In stepped data, the step number needs to be provided")
        else:
            if isinstance(step, (slice, int)):
                return self.dataset[measure][step]
            else:
                raise TypeError("Step must be an integer or a slice")

    def get_measure_values_at_steps(self, measure: str, steps: Union[None, int, Iterable]) \
            -> List[Union[float, int, str, LTComplex]]:
        """
        Returns the measurements taken at a list of steps provided by the steps list.

        :param measure: name of the measurement to get. This is case insensitive.
        :type measure: str
        :param steps: step number, or list of step numbers.
        :type steps: Optional: int or list
        :return: measurement or list of measurements
        :rtype: list with the values converted to either integer (int) or floating point (float)
        """
        measure = measure.lower()
        if steps is None:
            return self.dataset[measure]  # Returns everything
        elif isinstance(steps, int):
            return self.dataset[measure][steps]
        else:  # Assuming it is an iterable
            return [self.dataset[measure][step] for step in steps]

    def max_measure_value(self, measure: str, steps: Union[None, int, Iterable] = None) \
            -> Union[float, int, str]:
        """
        Returns the maximum value of a measurement.

        :param measure: name of the measurement to get. This is case insensitive.
        :type measure: str
        :param steps: step number, or list of step numbers.
        :type steps: Optional, int or list
        :return: maximum value of the measurement
        :rtype: float or int
        """
        return max(self.get_measure_values_at_steps(measure, steps))

    def min_measure_value(self, measure: str, steps: Union[None, int, Iterable] = None) \
            -> Union[float, int, str]:
        """
        Returns the minimum value of a measurement.

        :param measure: name of the measurement to get. This is case insensitive.
        :type measure: str
        :param steps: step number, or list of step numbers.
        :type steps: Optional: int or list
        :return: minimum value of the measurement
        :rtype: float or int
        """
        return min(self.get_measure_values_at_steps(measure, steps))

    def avg_measure_value(self, measure: str, steps: Union[None, int, Iterable] = None) \
            -> Union[float, int, str, LTComplex]:
        """
        Returns the average value of a measurement.

        :param measure: name of the measurement to get.  This is case insensitive.
        :type measure: str
        :param steps: step number, or list of step numbers.
        :type steps: Optional: int or list
        :return: average value of the measurement
        :rtype: float or int
        """
        values = self.get_measure_values_at_steps(measure, steps)
        return sum(values) / len(values)

    def obtain_amplitude_and_phase_from_complex_values(self):
        """
        Internal function to split the complex values into additional two columns.
        The two columns correspond to the magnitude and phase of the complex value in degrees.
        """
        for param in list(self.dataset.keys()):
            if len(self.dataset[param]) > 0 and isinstance(self.dataset[param][0], LTComplex):
                self.dataset[param + '_mag'] = [v.mag for v in self.dataset[param]]
                self.dataset[param + '_ph'] = [v.ph for v in self.dataset[param]]

    def split_complex_values_on_datasets(self):
        """
        .. deprecated:: 1.0 Use `obtain_amplitude_and_phase_from_complex_values()` instead.
        """
        self.obtain_amplitude_and_phase_from_complex_values()

    def export_data(self, export_file: str, encoding=None, append_with_line_prefix=None,
                    value_separator: str = '\t', line_terminator: str = '\n'):
        """
        Exports the measurement information to a tab separated value (.tsv) format. If step data is found, it is
        included in the exported file.

        When using export data together with SpiceBatch.py classes, it may be helpful to append data to an existing
        file. For this purpose, the user can user the append_with_line_prefix argument to indicate that an append should
        be done. And in this case, the user must provide a string that will identify the LTSpice batch run.

        :param export_file: path to the file containing the information
        :type export_file: str
        :param optional encoding: encoding to be used in the file
        :type encoding: str
        :param optional append_with_line_prefix: user information to be written in the file in case an append is to be made.
        :type append_with_line_prefix: str
        :param optional value_separator: character to be used to separate values
        :type value_separator: str
        :param optional line_terminator: Line terminator character
        :type line_terminator: str
        :return: Nothing
        """
        if append_with_line_prefix is None:
            mode = 'w'  # rewrites the file
        else:
            mode = 'a'  # Appends an existing file

        if len(self.dataset) == 0:
            _logger.warning("Empty data set. Exiting without writing file.")
            return

        if encoding is None:
            encoding = self.encoding if hasattr(self, 'encoding') else 'utf-8'

        fout = open(export_file, mode, encoding=encoding)

        if append_with_line_prefix is not None:  # if appending a file, it must write the column title
            fout.write('user info' + value_separator)

        data_size = None
        fout.write("step")
        columns_per_line = 1
        for title, values in self.stepset.items():
            if data_size is None:
                data_size = len(values)
            else:
                if len(values) != data_size:
                    raise Exception("Data size mismatch. Not all measurements have the same length.")

            if isinstance(values[0], list) and len(values[0]) > 1:
                for n in range(len(values[0])):
                    fout.write(value_separator + "%s_%d" % (title, n))
                    columns_per_line += 1
            else:
                fout.write(value_separator + title)
                columns_per_line += 1

        for title, values in self.dataset.items():
            if data_size is None:
                data_size = len(values)
            else:
                if len(values) != data_size:
                    logging.error(f"Data size mismatch. Not all measurements have the same length."
                                  f" Expected {data_size}. \"{title}\" has {len(values)}")

            if isinstance(values[0], list) and len(values[0]) > 1:
                for n in range(len(values[0])):
                    fout.write(value_separator + "%s_%d" % (title, n))
                    columns_per_line += 1
            else:
                fout.write(value_separator + title)
                columns_per_line += 1

        fout.write('\n')  # Finished to write the headers

        if data_size is None:
            data_size = 0  # Skips writing data in the loop below

        for index in range(data_size):
            if self.step_count == 0:
                step_data = []  # Empty step
            else:
                step_data = [self.stepset[param][index] for param in self.stepset.keys()]
            meas_data = [self.dataset[param][index] for param in self.dataset.keys()]

            if append_with_line_prefix is not None:  # if appending a file it must write the user info
                fout.write(append_with_line_prefix + value_separator)
            fout.write("%d" % (index + 1))
            columns_writen = 1
            for s in step_data:
                if isinstance(s, list):
                    for x in s:
                        fout.write(value_separator + f'{x}')
                        columns_writen += 1
                else:
                    fout.write(value_separator + f'{s}')
                    columns_writen += 1

            for tok in meas_data:
                if isinstance(tok, list):
                    for x in tok:
                        fout.write(value_separator + f'{x}')
                        columns_writen += 1
                else:
                    fout.write(value_separator + f'{tok}')
                    columns_writen += 1
            if columns_writen != columns_per_line:
                logging.error(f"Line with wrong number of values."
                              f" Expected:{columns_per_line} Index {index+1} has {columns_writen}")
            fout.write('\n')

        fout.close()

    def plot_histogram(self, param, steps: Union[None, int, Iterable] = None, bins=50, normalized=True, sigma=3.0, title=None, image_file=None, **kwargs):
        """
        Plots a histogram of the parameter
        """
        import numpy as np
        from scipy.stats import norm
        import matplotlib.pyplot as plt
        values = self.get_measure_values_at_steps(param, steps)
        x = np.array(values, dtype=float)
        mu = x.mean()
        mn = x.min()
        mx = x.max()
        sd = np.std(x)

        # Automatic calculation of the range
        axisXmin = mu - (sigma + 1) * sd
        axisXmax = mu + (sigma + 1) * sd

        if mn < axisXmin:
            axisXmin = mn

        if mx > axisXmax:
            axisXmax = mx

        n, bins, patches = plt.hist(x, bins, density=normalized, facecolor='green', alpha=0.75,
                                    range=(axisXmin, axisXmax))
        axisYmax = n.max() * 1.1

        if normalized:
            # add a 'best fit' line
            y = norm.pdf(bins, mu, sd)
            l = plt.plot(bins, y, 'r--', linewidth=1)
            plt.axvspan(mu - sigma * sd, mu + sigma * sd, alpha=0.2, color="cyan")
            plt.ylabel('Distribution [Normalised]')
        else:
            plt.ylabel('Distribution')
        plt.xlabel(param)

        if title is None:
            fmt = '%g'
            title = (r'$\mathrm{Histogram\ of\ %s:}\ \mu=' + fmt + r',\ stdev=' + fmt + r',\ \sigma=%d$') % (
                param, mu, sd, sigma)

        plt.title(title)

        plt.axis([axisXmin, axisXmax, 0, axisYmax])
        plt.grid(True)
        if image_file is not None:
            plt.savefig(image_file)
        else:
            plt.show()
