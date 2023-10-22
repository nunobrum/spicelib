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

from ...editor.base_editor import BaseEditor, scan_eng
from .sim_analysis import SimAnalysis, AnyRunner, ProcessCallback
from enum import Enum


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
        self.num_runs = 0
        self.simulation_results = {}

    def reset_tolerances(self):
        """
        Clears all the settings for the simulation
        """
        self.device_deviations.clear()
        self.parameter_deviations.clear()
        self.testbench_prepared = False
        self.num_runs = 0

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
            if value.startswith('{') and value.endswith('}'):
                # This is still acceptable as the value could be computed.
                # but we need to get rid of the outer {}
                value = value[1:-1]
            else:
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
        """The override of this method should set the self.testbench_prepared to True"""
        ...

    def run_testbench(self, *,
                      max_runs_per_sim: int = 512,
                      wait_resource: bool = True,
                      callback: Union[Type[ProcessCallback], Callable] = None,
                      callback_args: Union[tuple, dict] = None,
                      switches=None,
                      timeout: float = None,
                      run_filename: str = None):
        """
        Runs the simulations.
        :param max_runs_per_sim: Maximum number of runs per simulation. If the number of runs is higher than this
        number, the simulation is split in multiple runs.
        :param wait_resource: If True, the simulation will wait for the resource to be available. If False, the
        simulation will be queued and the method will return immediately.
        :param callback: A callback function to be called when the simulation is completed. The callback function must
        accept a single argument, which is the simulation object.
        :param callback_args: A tuple or dictionary with the arguments to be passed to the callback function.
        :param switches: A dictionary with the switches to be passed to the simulator.
        :param timeout: A timeout in seconds. If the simulation is not completed in this time, it will be aborted.
        :param run_filename: The name of the file to be used for the simulation. If None, a temporary file will be used.
        :return: The callback returns of every batch if a callback function is given. Otherwise, None.
        """
        if self.testbench_prepared is False:
            raise RuntimeError("The testbench is not prepared. Please call prepare_testbench() first")
        super()._reset_netlist()
        self.clear_simulation_data()
        self.play_instructions()
        self.prepare_testbench()
        self.editor.remove_instruction(".step param run -1 %d 1" % self.num_runs)  # Needs to remove this instruction
        for sim_no in range(-1, self.num_runs, max_runs_per_sim):
            last_no = sim_no + max_runs_per_sim - 1
            if last_no > self.num_runs:
                last_no = self.num_runs
            if sim_no >= last_no:
                break
            run_stepping = ".step param run {} {} 1".format(sim_no, last_no)
            self.editor.add_instruction(run_stepping)
            sim = self.runner.run(self.editor, wait_resource=wait_resource, callback=callback,
                                  callback_args=callback_args, switches=switches, timeout=timeout,
                                  run_filename=run_filename)
            self.simulations.append(sim)
            self.editor.remove_instruction(run_stepping)
        self.runner.wait_completion()
        if callback is not None:
            return (sim.get_results() if sim is not None else None for sim in self.simulations)
        self.testbench_executed = True
        return None

    def read_logfiles(self):
        """Returns the logdata for the simulations"""
        if self.analysis_executed is False and self.testbench_executed is False:
            raise RuntimeError("The analysis has not been executed yet")
        if 'log_data' in self.simulation_results:
            return self.simulation_results['log_data']
        else:
            log_data = super().read_logfiles()
            self.simulation_results['log_data'] = log_data
            return log_data

    @abstractmethod
    def run_analysis(self):
        """The override of this method should set the self.analysis_executed to True"""
        ...
