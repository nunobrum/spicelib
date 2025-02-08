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
# Name:        qspice_log_reader.py
# Purpose:     Read measurement data from a qspice log file
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     24-09-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import re
import logging
from pathlib import Path

from .logfile_data import LogfileData, try_convert_value, split_line_into_values
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
        self.logname = Path(log_filename)
        if encoding is None:
            self.encoding = 'utf-8'
        else:
            self.encoding = encoding

        step_regex = re.compile(r"^\s*(\d+) of \d+ steps:\s+\.step (.*)$")

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
                    for tok in tokens:
                        if '=' not in tok:
                            continue
                        lhs, rhs = tok.split("=")
                        # Try to convert to int or float
                        rhs = try_convert_value(rhs)
                        lhs = lhs.lower()
                        ll = self.stepset.get(lhs, None)
                        if ll:
                            ll.append(rhs)
                        else:
                            self.stepset[lhs] = [rhs]

                line = fin.readline()

        if read_measures:
            meas_file = self.obtain_measures()
            self.parse_meas_file(meas_file)

    def obtain_measures(self, meas_filename: Path = None) -> Path:
        """
        In QSpice the measures are obtained by calling the QPOST command giving as arguments
        the .qraw file and the .log file
        This function makes this call to QPOST and returns the measurement output file path.

        Note the call to QPOST includes the path to the circuit netlist. This is assumed to be the name of the
        logfile, but with the '.net' or '.cir' extension.

        :param meas_filename: This optional parameter specifies the measurement file name. If not given, it will
            assume the name of the log file but with the extension '.meas'.
        :type meas_filename: Optional str or Path
        :returns: The .meas file path
        :rtype: Path
        """
        if meas_filename is None:
            meas_filename = self.logname.with_suffix(".meas")
        elif not isinstance(meas_filename, Path):
            meas_filename = Path(meas_filename)

        if not Qspice.is_available():
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find the QSPICE executable.")
            _logger.error("A specific location of the QSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise RuntimeError("QSPICE not found in the usual locations. Please install it and try again.")

        # Get the QPOST location, which is the same as the QSPICE location
        qpost = [Qspice.spice_exe[0].replace("QSPICE64.exe", "QPOST.exe")]
        # Guess the name of the .net file
        netlist = self.logname.with_suffix('.net').absolute()
        if not Path.exists(netlist):
            netlist = self.logname.with_suffix('.cir').absolute()
                    
        # Run the QPOST command
        cmd_run = qpost + [netlist, "-o", meas_filename.absolute()]
        _logger.debug(f"Running QPOST command: {cmd_run}")
        run_function(cmd_run)
        return meas_filename

    def parse_meas_file(self, meas_filename):
        """
        Parses the .meas file and reads all measurements contained in the file. Access to the measurements is done
        using this class interface.

        :param meas_filename: path to the measurement file to parse.
        :type meas_filename: str or Path
        :returns: Nothing
        """
        meas_regex = re.compile(r"^\.meas (\w+) (\w+) (.*)$")
        meas_name = None
        headers = None

        with open(meas_filename, 'r', encoding=self.encoding) as fin:
            line = fin.readline()
            while line:
                match = meas_regex.match(line)
                if match:
                    headers = None
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
                else:
                    if meas_name:
                        values = split_line_into_values(line)
                        if headers is None:
                            if self.has_steps():
                                headers = ['step'] + [meas_name + "_" + str(i) for i in range(len(values) - 1)]
                                headers[1] = meas_name  # first column is the measure name without _0
                            else:
                                headers = [meas_name + "_" + str(i) for i in range(len(values))]
                                headers[0] = meas_name  # first column is the measure name without _0

                            for title in headers:
                                self.dataset[title.lower()] = []
                        self.measure_count += 1
                        for k, title in enumerate(headers):
                            self.dataset[title.lower()].append(values[k])
                line = fin.readline()
