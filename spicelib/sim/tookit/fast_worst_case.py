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
# Name:        fast_worst_case.py
# Purpose:     Class to automate Worst-Case simulations (Faster Algorithm)
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     04-11-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from time import sleep
from typing import Union, Callable, Type
from enum import IntEnum

from .worst_case import WorstCaseAnalysis, DeviationType, ToleranceDeviations
from ..process_callback import ProcessCallback
from ...log.logfile_data import LogfileData

_logger = logging.getLogger("spicelib.SimAnalysis")


class WorstCaseType(IntEnum):
    nom = 0
    max = 1
    min = 2


class FastWorstCaseAnalysis(WorstCaseAnalysis):
    """
    This class implements a faster algorithm to perform a worst case analysis. The typical worst case analysis makes
    all possible combinations of the components that have a deviation. This means that if there are 10 components with
    a deviation, there will be 1024 simulations to be performed. The number of simulations grows exponentially with the
    number of components with deviation.

    This algorithm speeds up the process, by determining the impact of each component with deviation on the final
    result and skipping simulations that are not necessary. The algorithm is as follows:

        1. Make a sensitivity analysis to determine the impact that each component has on the final result.

        2. Based on the information collected on 1. set all the components with deviation achieve a maximum
        on the final result. Components are set based on the assumption that the system is reaction is to each
        component is monotonic. That is, if increasing the component value, increases the final result, then the
        component is set to the maximum value. If decreasing the component value increases the final result, then the
        component is set to the minimum value.

        3. Validate the assumption based on 2. by making a series of test simulations setting each component with their
        opposite value. If the result is lower, then the assumption is correct. If the result is higher, then the
        assumption is wrong and the component is set to the opposite value.

        4. Repeat 2. but this time trying to achieve a minimum on the final result.

        5. Repeat step 3. but this time trying to achieve a minimum on the final result.

    Like in the Worst-Case and Montecarlo, there are two approaches to make this analysis. Either preparing a testbench
    where component variations are managed by the simulator, or by ordering each simulation individually.
    In the testbench method all component values are replaced by formulas that depend on a .STEP PARAM run, and
    then run_testbench() will make all the manipulations of the run variable.

    In the latter, each component value is set individually. This is done by calling the run_analysis() method.
    """

    def run_testbench(
            self, *,
            max_runs_per_sim: int = None,  # This parameter is ignored
            wait_resource: bool = True, # This parameter is ignored
            callback: Union[Type[ProcessCallback], Callable] = None,
            callback_args: Union[tuple, dict] = None,
            switches=None,
            timeout: float = None,
            run_filename: str = None) -> None:
        raise NotImplementedError("run_testbench() is not implemented in this class")

    def run_analysis(self,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     measure: str = None,
                     ):
        """
        As described in the class description, this method will perform a worst case analysis using a faster algorithm.
        """
        assert measure is not None, "The measure argument must be defined"

        self.clear_simulation_data()
        worst_case_elements = {}

        def check_and_add_component(ref1: str):
            val1, dev1 = self.get_component_value_deviation_type(ref1)  # get there present value
            if dev1.min_val == dev1.max_val or dev1.typ == DeviationType.none:
                return
            worst_case_elements[ref1] = val1, dev1, 'component'
            self.elements_analysed.append(ref1)

        def set_ref_to(ref, to: WorstCaseType):
            """
            Sets the reference component to the maximum value if set_max is True, or to the minimum value if set_max is
            False. This method is used by the run_analysis() method.
            """
            # Preparing the variation on components, but only on the ones that have changed
            val, dev, typ = worst_case_elements[ref]
            if dev.typ == DeviationType.tolerance:
                if to == WorstCaseType.max:
                    new_val = val * (1 + dev.max_val)
                elif to == WorstCaseType.min:
                    new_val = val * (1 - dev.max_val)
                else:
                    # Default to nominal case
                    new_val = val

            elif dev.typ == DeviationType.minmax:
                if to == WorstCaseType.max:
                    new_val = dev.max_val
                elif to == WorstCaseType.min:
                    new_val = dev.min_val
                else:
                    # Default to nominal case
                    new_val = val
            else:
                _logger.warning("Unknown deviation type")
                new_val = val
            if typ == 'component':
                self.editor.set_component_value(ref, new_val)  # update the value
            elif typ == 'parameter':
                self.editor.set_parameter(ref, new_val)
            else:
                _logger.warning("Unknown type")

        for ref in self.device_deviations:
            check_and_add_component(ref)

        for ref in self.parameter_deviations:
            val, dev = self.get_parameter_value_deviation_type(ref)
            if dev.typ == DeviationType.tolerance or dev.typ == DeviationType.minmax:
                worst_case_elements[ref] = val, dev, 'parameter'
                self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    check_and_add_component(ref)

        _logger.info("Worst Case Analysis: %d elements to be analysed", len(self.elements_analysed))

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        # Simulate the nominal case
        self.run(self.editor, wait_resource=True,
                 callback=callback, callback_args=callback_args,
                 switches=switches, timeout=timeout)

        # Sequence a change of a component value at a time, setting it to the maximum value
        for ref in self.elements_analysed:
            set_ref_to(ref, WorstCaseType.max)
            # Run the simulation
            self.run(self.editor, wait_resource=True,
                     callback=callback, callback_args=callback_args,
                     switches=switches, timeout=timeout)
        self.runner.wait_completion()

        # Get the results from the simulation
        log_data = self.read_logfiles()
        nominal = log_data.get_measure_value(measure, 0)
        _logger.info("Nominal value: %g", nominal)
        component_deltas = {}
        idx = 1
        last_measure = nominal
        for ref in self.elements_analysed:
            component_deltas[ref] = log_data.get_measure_value(measure, idx) - last_measure
            _logger.info("Component %s: %g", ref, component_deltas[ref])
            idx += 1
        # Check which components have a positive impact on the final result, that is, increasing the component value
        # increases the final result
        negative = [ref for ref in component_deltas if component_deltas[ref] < 0]

        # Set all components with a positive impact to the maximum value and all components with a negative impact to
        # the minimum value
        for ref in negative:
            set_ref_to(ref, WorstCaseType.min)
