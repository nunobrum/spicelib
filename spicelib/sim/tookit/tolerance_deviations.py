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
# Name:        montecarlo.py
# Purpose:     Classes to automate Monte-Carlo simulations
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Union, Optional, Dict, Callable, Type

from ..run_task import RunTask
from ...editor.base_editor import BaseEditor, scan_eng
from .sim_analysis import SimAnalysis, AnyRunner, ProcessCallback
from enum import Enum

from ...log.logfile_data import LTComplex, LogfileData


class DeviationType(Enum):
    """Enum to define the type of deviation"""
    tolerance = 'tolerance'
    minmax = 'minmax'
    none = 'none'


@dataclass
class ComponentDeviation:
    """Class to store the deviation of a component"""
    max_val: float
    min_val: float = 0.0
    typ: DeviationType = DeviationType.tolerance
    distribution: str = 'uniform'

    @classmethod
    def from_tolerance(cls, tolerance: float, distribution: str = 'uniform'):
        return cls(tolerance, -tolerance, DeviationType.tolerance, distribution)

    @classmethod
    def from_min_max(cls, min_val: float, max_val: float, distribution: str = 'uniform'):
        return cls(min_val, max_val, DeviationType.minmax, distribution)

    @classmethod
    def none(cls):
        return cls(0.0, 0.0, DeviationType.none)


class ToleranceDeviations(SimAnalysis, ABC):
    """Class to automate Monte-Carlo simulations"""
    devices_with_deviation_allowed = ('R', 'C', 'L', 'V', 'I')

    def __init__(self, circuit_file: Union[str, BaseEditor], runner: Optional[AnyRunner] = None):
        super().__init__(circuit_file, runner)
        self.default_tolerance = {prefix: ComponentDeviation.none() for prefix in self.devices_with_deviation_allowed}
        self.device_deviations: Dict[str, ComponentDeviation] = {}
        self.parameter_deviations: Dict[str, ComponentDeviation] = {}
        self.testbench_prepared = False
        self.testbench_executed = False
        self.analysis_executed = False
        self.last_run_number = 0
        self.simulation_results = {}
        self.elements_analysed = []

    def reset_tolerances(self):
        """
        Clears all the settings for the simulation
        """
        self.device_deviations.clear()
        self.parameter_deviations.clear()
        self.testbench_prepared = False
        self.last_run_number = 0

    def clear_simulation_data(self):
        """Clears the data from the simulations"""
        super().clear_simulation_data()
        self.simulation_results.clear()
        self.analysis_executed = False

    def set_tolerance(self, ref: str, new_tolerance: float, distribution: str = 'uniform'):
        """
        Sets the tolerance for a given component. If only the prefix is given, the tolerance is set for all.
        The valid prefixes that can be used are: R, C, L, V, I
        """
        if ref in self.devices_with_deviation_allowed:  # Only the prefix is given
            self.default_tolerance[ref] = ComponentDeviation.from_tolerance(new_tolerance, distribution)
        else:
            if ref in self.editor.get_components(ref[0]):
                self.device_deviations[ref] = ComponentDeviation.from_tolerance(new_tolerance, distribution)

    def set_tolerances(self, new_tolerances: dict, distribution: str = 'uniform'):
        """
        Sets the tolerances for a set of components. The dictionary keys are the references and the values are the
        tolerances. If only the prefix is given, the tolerance is set for all components with that prefix. See
        set_tolerance method.
        """
        for ref, tol in new_tolerances.items():
            self.set_tolerance(ref, tol, distribution)

    def set_deviation(self, ref: str, min_val, max_val: float, distribution: str = 'uniform'):
        """
        Sets the deviation for a given component. This establishes a min and max value for the component.
        Optionally a distribution can be specified. The valid distributions are: uniform or normal (gaussian).
        """
        self.device_deviations[ref] = ComponentDeviation.from_min_max(min_val, max_val, distribution)

    def get_components(self, prefix: str):
        if prefix == '*':
            return (cmp for cmp in self.editor.get_components() if cmp[0] in self.devices_with_deviation_allowed)
        return self.editor.get_components(prefix)

    def get_component_value_deviation_type(self, ref: str) -> (float, ComponentDeviation):
        if ref[0] not in self.devices_with_deviation_allowed:
            raise ValueError("The reference must be a valid component type")
        value = self.editor.get_component_value(ref)
        if len(value) == 0:  # This covers empty strings
            return value, ComponentDeviation.none()
        # The value needs to be able to be computed, otherwise it can't be used
        try:
            value = scan_eng(value)
        except ValueError:
            return value, ComponentDeviation.none()
        if ref in self.device_deviations:
            return value, self.device_deviations[ref]
        elif ref[0] in self.default_tolerance:
            return value, self.default_tolerance[ref[0]]
        else:
            return value, ComponentDeviation.none()

    def set_parameter_deviation(self, ref: str,  min_val, max_val: float, distribution: str = 'uniform'):
        self.parameter_deviations[ref] = ComponentDeviation.from_min_max(min_val, max_val, distribution)

    def get_parameter_value_deviation_type(self, param: str) -> (float, ComponentDeviation):
        value = self.editor.get_parameter(param)
        return value, self.parameter_deviations[param]

    def save_netlist(self, filename: str):
        if self.testbench_prepared is False:
            self.prepare_testbench()
        super().save_netlist(filename)

    def _reset_netlist(self):
        super()._reset_netlist()
        self.testbench_prepared = False

    @abstractmethod
    def prepare_testbench(self, **kwargs):
        ...

    def run_testbench(self, *,
                      runs_per_sim: int = 512,
                      wait_resource: bool = True,
                      callback: Union[Type[ProcessCallback], Callable] = None,
                      callback_args: Union[tuple, dict] = None,
                      switches=None,
                      timeout: float = None,
                      run_filename: str = None,
                      exe_log: bool = False,
                      ):
        """
        Runs the simulations.
        :param runs_per_sim: Maximum number of runs per simulation. If the number of runs is higher than this
        number, the simulation is split in multiple runs.
        :param wait_resource: If True, the simulation will wait for the resource to be available. If False, the
        simulation will be queued and the method will return immediately.
        :param callback: A callback function to be called when the simulation is completed. The callback function must
        accept a single argument, which is the simulation object.
        :param callback_args: A tuple or dictionary with the arguments to be passed to the callback function.
        :param switches: A dictionary with the switches to be passed to the simulator.
        :param timeout: A timeout in seconds. If the simulation is not completed in this time, it will be aborted.
        :param run_filename: The name of the file to be used for the simulation. If None, a temporary file will be used.
        :param exe_log: Sends the execution log_file to a file "netlist_name.exe.log".
        :return: The callback returns of every batch if a callback function is given. Otherwise, None.
        """
        if self.testbench_prepared is False:
            super()._reset_netlist()
            self.play_instructions()
            self.prepare_testbench()
        else:
            self.play_instructions()
        self.editor.remove_instruction(".step param run -1 %d 1" % self.last_run_number)  # removes this instruction
        self.clear_simulation_data()
        # calculate the ideal number of runs per simulation to avoid orphan runs. This is to avoid having a simulation
        # with only one run. Which poses a problem for .step instruction
        total_number_of_runs = self.last_run_number + 2  # the +2 is to account for the run -1 and the last run
        runs_per_sim = min(runs_per_sim, total_number_of_runs)
        while total_number_of_runs % runs_per_sim == 1:  # Avoid orphan runs
            runs_per_sim += 1

        for sim_no in range(-1, self.last_run_number + 1, runs_per_sim):
            last_no = sim_no + runs_per_sim - 1
            if last_no > self.last_run_number:
                last_no = self.last_run_number

            run_stepping = ".step param run {} {} 1".format(sim_no, last_no)
            self.editor.add_instruction(run_stepping)
            sim = self.runner.run(self.editor, wait_resource=wait_resource, callback=callback,
                                  callback_args=callback_args, switches=switches, timeout=timeout,
                                  run_filename=run_filename, exe_log=exe_log)
            self.simulations.append(sim)
            self.editor.remove_instruction(run_stepping)
        self.runner.wait_completion()
        if callback is not None:
            return (sim.get_results() if sim is not None else None for sim in self.simulations)
        self.testbench_executed = True
        return None

    def add_log(self, run_task: RunTask) -> Union[LogfileData, None]:
        """Reads a log file and adds it to the simulation_results. It does so making sure that the run number is
        correctly set."""
        if run_task.retcode != 0:
            return None

        log_results = self.read_logfile(run_task)
        if len(log_results.stepset) == 0:
            if 'run' in log_results.dataset and len(log_results.dataset['run']) > 0:
                if isinstance(log_results.dataset['run'][0], LTComplex):
                    log_results.stepset = {'run': [round(val.real) for val in log_results.dataset['run']]}
                else:
                    log_results.stepset = {'run': log_results.dataset['run']}
            else:
                # auto assign a step starting from 0 and incrementing by 1
                # will use the size of the first element found in the dataset
                any_meas = next(iter(log_results.dataset.values()))
                run_start = self.log_data.stepset['run'][-1] + 1 if len(self.log_data.stepset) > 0 else 0
                log_results.stepset = {'run': list(range(run_start, run_start + len(any_meas)))}

            log_results.step_count = len(log_results.stepset)

        self.add_log_data(log_results)
        return log_results

    def read_logfiles(self):
        """Returns the logdata for the simulations"""
        if self.analysis_executed is False and self.testbench_executed is False:
            raise RuntimeError("The analysis has not been executed yet")

        if 'log_data' in self.simulation_results:
            return self.simulation_results['log_data']

        super().read_logfiles()
        # The code below makes the run measure (if it exists) available on the stepset.
        # Note: this was only tested with LTSpice
        if len(self.log_data.stepset) == 0:
            if 'runm' in self.log_data.dataset and len(self.log_data.dataset['runm']) > 0:
                if isinstance(self.log_data.dataset['runm'][0], LTComplex):
                    self.log_data.stepset = {'run': [round(val.real) for val in self.log_data.dataset['runm']]}
                else:
                    self.log_data.stepset = {'run': self.log_data.dataset['runm']}
            else:
                # auto assign a step starting from 0 and incrementing by 1
                # will use the size of the first element found in the dataset
                any_meas = next(iter(self.log_data.dataset.values()))
                self.log_data.stepset = {'run': list(range(len(any_meas)))}
            self.log_data.step_count = len(self.log_data.stepset)

        self.simulation_results['log_data'] = self.log_data
        return self.log_data

    @abstractmethod
    def run_analysis(self,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     exe_log: bool = True,
                     ):
        """The override of this method should set the self.analysis_executed to True"""
        ...
