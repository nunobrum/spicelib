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
# Name:        qspice_log_reder.py
# Purpose:     Read measurement data from a qspice log file
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     24-09-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import re
import logging
from .logfile_data import LogfileData, try_convert_value
from ..sim.simulator import run_function
from ..simulators.qspice_simulator import Qspice

_logger = logging.getLogger("spicelib.qspice_log_reader")


class QspiceLogReader(LogfileData):
    """
    Reads an QSpice log file and retrieves the step and measurement information if it exists.
    The step information is then accessible by using the 'stepset' property of this class.
    This class is intended to be used together with the RawRead to retrieve the runs that are associated with a
    given parameter setting.

    This class constructor only reads the step information of the log file. If the measures are needed, then the user
    should call the get_measures() method.

    :property stepset: dictionary in which the keys are the variables that were STEP'ed during the simulation and
        the associated value is a list representing the sequence of assigned values during simulation.

    :property headers: list containing the headers on the exported data. This is only populated when the *read_measures*
        optional parameter is set to False.

    :property dataset: dictionary in which the keys are the the headers and the export file and the values are
         lists. This is information is only populated when the *read_measures* optional parameter is set to False.

    :param log_filename: path to the Export file.
    :type log_filename: str
    :param read_measures: Optional parameter to skip measuring data reading.
    :type read_measures: boolean
    :param step_set: Optional parameter to provide the steps from another file. This is used to process .mout files.
    :type step_set: dict
    """

    def __init__(self, log_filename: str, read_measures=True, step_set: dict = None, encoding=None):
        super().__init__(step_set)
        self.logname = log_filename
        if encoding is None:
            self.encoding = 'utf-8'
        else:
            self.encoding = encoding

        step_regex = re.compile(r"^(\d+) of \d+ steps:\s+\.step (.*)$")

        _logger.debug(f"Processing LOG file:{log_filename}")
        with open(log_filename, 'r', encoding=self.encoding) as fin:
            line = fin.readline()
            while line:
                match = step_regex.match(line)
                if match:
                    self.step_count += 1
                    step = int(match.group(1))
                    stepset = match.group(2)
                    assert self.step_count == step, f"Step count mismatch: {self.step_count} != {step}"
                    _logger.debug(f"Found step {step} with stepset {stepset}")

                    tokens = stepset.strip('\r\n').split(' ')
                    for tok in tokens[1:]:
                        lhs, rhs = tok.split("=")
                        # Try to convert to int or float
                        rhs = try_convert_value(rhs)

                        ll = self.stepset.get(lhs, None)
                        if ll:
                            ll.append(rhs)
                        else:
                            self.stepset[lhs] = [rhs]

                line = fin.readline()

        if read_measures:
            meas_file = self.obtain_measures()
            self.parse_meas_file(meas_file)

    def obtain_measures(self, meas_filename=None):
        """
        In QSpice the measures are obtained by calling the QPOST command giving as arguments
        the .qraw file and the .log file
        """
        # Get the QPOST location, which is the same as the QSPICE location
        qpost = [Qspice.spice_exe[0].replace("QSPICE64.exe", "QPOST.exe")]
        # Guess the name of the .qraw file
        netlist = self.logname.with_suffix('.net')
        # Run the QPOST command
        if meas_filename is None:
            meas_filename = self.logname.with_suffix(".meas")
        cmd_run = qpost + [netlist.absolute(), "-o", meas_filename.absolute()]
        _logger.debug(f"Running QPOST command: {cmd_run}")
        run_function(cmd_run)
        return meas_filename


    def parse_meas_file(self, meas_filename):
        """
        Parses the .meas file and populates the dataset and headers properties.
        """
        meas_regex = re.compile(r"^\.meas (\w+) (\w+) (.*)$")
        with open(meas_filename, 'r', encoding=self.encoding) as fin:
            line = fin.readline()
            while line:
                match = meas_regex.match(line)
                if match:
                    token1 = match.group(1)
                    token2 = match.group(2)
                    if token1 in ('tran', 'ac', 'dc', 'op'):
                        sim_type = token1
                        meas_name = token2
                    else:
                        sim_type = token2
                        meas_name = token1
                    meas_expr = match.group(3)
                    _logger.debug(f"Found measure {meas_name} of type {sim_type} with expression {meas_expr}")
                    line = fin.readline().strip()  # values are found in the next line
                    if line.startswith('(') and line.endswith(')'):
                        line = line[1:-1]  # remove the parenthesis
                        values = line.strip().split(',')
                    else:
                        values = line.strip().split(' ')
                    headers = [meas_name + "_" + str(i) for i in range(len(values))]
                    headers[0] = meas_name  # first column is the measure name without _0
                    self.measure_count += 1
                    for k, title in enumerate(headers):
                        self.dataset[title] = [
                            try_convert_value(values[k])]  # need to be a list for compatibility
                line = fin.readline()
