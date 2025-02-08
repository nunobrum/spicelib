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
# Name:        sim_analysis.py
# Purpose:     Classes to automate Monte-Carlo, FMEA or Worst Case Analysis
#              be updated by user instructions
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     06-07-2021
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from pathlib import Path
from typing import Union, Optional, Type, Callable
import logging
from ..sim_runner import AnyRunner, RunTask, ProcessCallback
from ...editor.base_editor import BaseEditor
from ...log.logfile_data import LogfileData
from ...utils.detect_encoding import EncodingDetectError

from ...log.ltsteps import LTSpiceLogReader
from ...log.qspice_log_reader import QspiceLogReader

_logger = logging.getLogger("spicelib.SimAnalysis")

class SimAnalysis(object):
    """
    Base class for making Monte-Carlo, Extreme Value Analysis (EVA) or Failure Mode and Effects Analysis.
    As a base class, a certain number of assertions must be made on the simulation results that will make the pass/fail.

    Note: For the time being only measurements done with .MEAS are possible. At a later stage the parsing of RAW files
    will be possible, although, it seems that the later solution is less computing intense.
    """

    def __init__(self, circuit_file: Union[str, BaseEditor], runner: Optional[AnyRunner] = None):
        if isinstance(circuit_file, str):
            from ...editor.spice_editor import SpiceEditor
            self.editor = SpiceEditor(circuit_file)
        else:
            self.editor = circuit_file
        self._runner = runner
        self.simulations = []
        self.last_run_number = 0
        self.received_instructions = []
        self.instructions_added = False
        self.log_data = LogfileData()

    def clear_simulation_data(self):
        """Clears the data from the simulations"""
        self.simulations.clear()

    @property
    def runner(self):
        if self._runner is None:
            from ...sim.sim_runner import SimRunner
            self._runner = SimRunner()
        return self._runner

    @runner.setter
    def runner(self, new_runner: AnyRunner):
        self._runner = new_runner

    def run(self, *,
            wait_resource: bool = True,
            callback: Union[Type[ProcessCallback], Callable] = None,
            callback_args: Union[tuple, dict] = None,
            switches=None,
            timeout: float = None,
            run_filename: str = None,
            exe_log: bool = True,
            ) -> Union[RunTask, None]:
        """
        Runs the simulations. See runner.run() method for details on arguments.
        """
        sim = self.runner.run(self.editor,
                              wait_resource=wait_resource,
                              callback=callback,
                              callback_args=callback_args,
                              switches=switches,
                              timeout=timeout,
                              run_filename=run_filename,
                              exe_log=exe_log)
        if sim is not None:
            self.simulations.append(sim)
            return sim

    def wait_completion(self):
        self.runner.wait_completion()

    @wraps(BaseEditor.reset_netlist)
    def reset_netlist(self):
        """Resets the netlist to the original state and clears the instructions added by the user."""
        self._reset_netlist()
        self.received_instructions.clear()

    def _reset_netlist(self):
        """Unlike the reset_netlist method of the BaseEditor, this method does not clear the instructions added by the
        user. This is useful for the case where the user wants to run multiple simulations with different parameters
        without having to add the instructions again."""
        self.editor.reset_netlist()
        self.instructions_added = False

    def set_component_value(self, ref: str, new_value: str):
        self.received_instructions.append(('set_component_value', ref, new_value))

    def set_element_model(self, ref: str, new_model: str):
        self.received_instructions.append(('set_element_model', ref, new_model))

    def set_parameter(self, ref: str, new_value: str):
        self.received_instructions.append(('set_parameter', ref, new_value))

    def add_instruction(self, new_instruction: str):
        self.received_instructions.append(('add_instruction', new_instruction))

    def remove_instruction(self, instruction: str):
        self.received_instructions.append(('remove_instruction', instruction))

    def remove_Xinstruction(self, search_pattern: str):
        self.received_instructions.append(('remove_Xinstruction', search_pattern))

    def play_instructions(self):
        if self.instructions_added:
            return  # Nothing to do
        for instruction in self.received_instructions:
            if instruction[0] == 'set_component_value':
                self.editor.set_component_value(instruction[1], instruction[2])
            elif instruction[0] == 'set_element_model':
                self.editor.set_element_model(instruction[1], instruction[2])
            elif instruction[0] == 'set_parameter':
                self.editor.set_parameter(instruction[1], instruction[2])
            elif instruction[0] == 'add_instruction':
                self.editor.add_instruction(instruction[1])
            elif instruction[0] == 'remove_instruction':
                self.editor.remove_instruction(instruction[1])
            elif instruction[0] == 'remove_Xinstruction':
                self.editor.remove_Xinstruction(instruction[1])
            else:
                raise ValueError("Unknown instruction")
        self.instructions_added = True

    def save_netlist(self, filename: str):
        self.play_instructions()
        self.editor.save_netlist(filename)

    def cleanup_files(self):
        """Clears all simulation files. Typically used after a simulation run and analysis."""
        self.runner.cleanup_files()

    def simulation(self, index: int):
        """Returns a simulation object"""
        return self.simulations[index]

    def __getitem__(self, item):
        return self.simulations[item]

    @staticmethod
    def read_logfile(run_task: RunTask) -> Union[LogfileData, None]:
        """Reads the log file and returns a dictionary with the results"""
        if run_task.simulator.__name__ == "LTspice":
            LogReader = LTSpiceLogReader
        elif run_task.simulator.__name__ == "Qspice":
            LogReader = QspiceLogReader
        else:
            raise ValueError("Unknown simulator type")

        try:
            log_results = LogReader(run_task.log_file)
        except FileNotFoundError:
            _logger.warning("Log file not found: %s", run_task.log_file)
            return None
        except EncodingDetectError:
            _logger.warning("Log file %s couldn't be read", run_task.log_file)
            return None
        return log_results

    def add_log_data(self, log_data: LogfileData):
        """Add data from a log file to the log_data object"""
        if log_data is None:
            return

        for param in log_data.stepset:
            if param not in self.log_data.stepset:
                self.log_data.stepset[param] = log_data.stepset[param]
            else:
                self.log_data.stepset[param].extend(log_data.stepset[param])
        for param in log_data.dataset:
            if param not in self.log_data.dataset:
                self.log_data.dataset[param] = log_data.dataset[param][:]
            else:
                self.log_data.dataset[param].extend(log_data.dataset[param][:])
        self.log_data.step_count += log_data.step_count

    def read_logfiles(self) -> LogfileData:
        """Reads the log files and returns a dictionary with the results"""
        self.log_data = LogfileData()  # Clears the log data
        for sim in self.simulations:
            if sim is None:
                continue

            log_results = self.read_logfile(sim)
            self.add_log_data(log_results)

        return self.log_data

    def configure_measurement(self, meas_name: str, meas_expression: str, meas_type: str = 'tran'):
        """Configures a measurement to be done in the simulation"""
        self.editor.add_instruction(".meas {} {} {}".format(meas_type, meas_name, meas_expression))
