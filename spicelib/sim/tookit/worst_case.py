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
# Name:        worst_case.py
# Purpose:     Classes to automate Worst-Case simulations
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from typing import Union, Callable, Type

from .tolerance_deviations import ToleranceDeviations, DeviationType
from ..process_callback import ProcessCallback
from ...log.logfile_data import LogfileData

_logger = logging.getLogger("spicelib.SimAnalysis")


class WorstCaseAnalysis(ToleranceDeviations):
    """Class to automate Monte-Carlo simulations"""

    def _set_component_deviation(self, ref: str, index) -> bool:
        """Sets the deviation of a component. Returns True if the component is valid and the deviation was set.
        Otherwise, returns False"""
        val, dev = self.get_component_value_deviation_type(ref)  # get there present value
        if dev.min_val == dev.max_val:
            return False  # no need to set the deviation
        new_val = val
        if dev.typ == DeviationType.tolerance:
            new_val = "{wc(%s,%g,%d)}" % (val, dev.max_val, index)  # calculate expression for new value
        elif dev.typ == DeviationType.minmax:
            new_val = "{wc1(%s,%g,%g,%d)}" % (val, dev.min_val, dev.max_val, index)  # calculate expression for new value

        if new_val != val:
            self.set_component_value(ref, new_val)  # update the value
            self.elements_analysed.append(ref)
        return True

    def prepare_testbench(self, **kwargs):
        """Prepares the simulation by setting the tolerances for the components"""
        index = 0
        for ref in self.device_deviations:
            if self._set_component_deviation(ref, index):
                index += 1
        for ref in self.parameter_deviations:
            val, dev = self.get_parameter_value_deviation_type(ref)
            new_val = val
            if dev.typ == DeviationType.tolerance:
                new_val = "{wc(%s,%g,%d)}" % (val, dev.max_val, index)  # calculate expression for new value
            elif dev.typ == DeviationType.minmax:
                new_val = "{wc1(%s,%g,%g,%d)}" % (val, dev.min_val, dev.max_val, index)
            if new_val != val:
                self.editor.set_parameter(ref, new_val)
            index += 1

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    if self._set_component_deviation(ref, index):
                        index += 1

        self.editor.add_instruction(".func binary(run,idx) floor(run/(2**idx))-2*floor(run/(2**(idx+1)))")
        self.editor.add_instruction(".func wc(nom,tol,idx) {nom*if(binary(run,idx),1-tol,1+tol)}")
        self.editor.add_instruction(".func wc1(nom,min,max,idx) {nom*if(binary(run,idx),min,max)}")
        self.last_run_number = 2**index - 1
        self.editor.add_instruction(".step param run -1 %d 1" % self.last_run_number)
        self.editor.set_parameter('run', -1)  # in case the step is commented.
        self.testbench_prepared = True

    def run_analysis(self,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     ):
        """This method runs the analysis without updating the netlist.
        It will update component values and parameters according to their deviation type and call the simulation.
        The advantage of this method is that it doesn't require adding random functions to the netlist."""
        self.clear_simulation_data()
        worst_case_elements = {}

        def check_and_add_component(ref1: str):
            val1, dev1 = self.get_component_value_deviation_type(ref1)  # get there present value
            if dev1.min_val == dev1.max_val or dev1.typ == DeviationType.none:
                return
            worst_case_elements[ref1] = val1, dev1, 'component'
            self.elements_analysed.append(ref1)

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

        # Calculate the number of runs
        last_run_number = 2**len(self.elements_analysed) - 1
        if last_run_number >= 4095:
            _logger.warning("The number of runs is too high. It will be limited to 4096\n"
                            "Consider limiting the number of components with deviation")
            return

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        self.editor.set_parameter('run', -1)  # This is aligned with the testbench preparation
        # Simulate the nominal case
        self.run(self.editor, wait_resource=True,
                 callback=callback, callback_args=callback_args,
                 switches=switches, timeout=timeout)
        self.runner.wait_completion()
        # Simulate the worst case
        last_run = 2 ** len(self.elements_analysed) - 1  # Sets all valid bits to 1
        for run in range(0, last_run_number):
            # Preparing the variation on components, but only on the ones that have changed
            bit_updated = run ^ last_run
            bit_index = 0
            while bit_updated != 0:
                if bit_updated & 1:
                    ref = self.elements_analysed[bit_index]
                    val, dev, typ = worst_case_elements[ref]
                    if dev.typ == DeviationType.tolerance:
                        new_val = val * (1 - dev.max_val) if run & (1 << bit_index) else val * (1 + dev.max_val)
                    elif dev.typ == DeviationType.minmax:
                        new_val = dev.min_val if run & (1 << bit_index) else dev.max_val
                    else:
                        _logger.warning("Unknown deviation type")
                        new_val = val
                    if typ == 'component':
                        self.editor.set_component_value(ref, new_val)  # update the value
                    elif typ == 'parameter':
                        self.editor.set_parameter(ref, new_val)
                    else:
                        _logger.warning("Unknown type")
                bit_updated >>= 1
                bit_index += 1

            self.editor.set_parameter('run', run)
            # Run the simulation
            self.run(self.editor, wait_resource=True,
                     callback=callback, callback_args=callback_args,
                     switches=switches, timeout=timeout)
            last_run = run
        self.runner.wait_completion()

        if callback is not None:
            callback_rets = []
            for rt in self.simulations:
                callback_rets.append(rt.get_results())
            self.simulation_results['callback_returns'] = callback_rets
        self.analysis_executed = True

    def get_min_max_measure_value(self, meas_name: str):
        """Returns the minimum and maximum values of a measurement"""
        if not self.analysis_executed:
            _logger.warning("The analysis was not executed. Please run the analysis before calling this method")
            return None

        log_data: LogfileData = self.read_logfiles()
        meas_data = log_data[meas_name]
        if meas_data is None:
            _logger.warning("Measurement %s not found in log files", meas_name)
            return None
        elif len(meas_data) != len(self.simulations):
            _logger.warning("Missing log files. Results may not be reliable. Probable cause are:\n"
                            "  - Failed simulations.\n"
                            "  - Measurement couldn't be done in simulation results.")
        else:
            return min(meas_data), max(meas_data)

    def make_sensitivity_analysis(self, measure: str, ref: str = '*'):
        """Makes a sensitivity analysis for a given measurement and reference component"""
        if self.testbench_prepared and self.testbench_executed or self.analysis_executed:
            # Read the log files
            log_data: LogfileData = self.read_logfiles()
            nominal_data = log_data.get_measure_value(measure, run=-1)
            error_data = []
            for idx, ref in enumerate(self.elements_analysed):
                # For sensitivity, we take all measurements with the ref at maximum and subtract with the respective
                # measurement when the ref is at its minimum.
                step_data = log_data.get_measure_value(measure, run=idx)
                error_data.append(abs(step_data - nominal_data))
            total_error = sum(error_data)
            if ref == '*':
                return {ref: error_data[idx] / total_error * 100 if total_error != 0 else 0
                        for idx, ref in enumerate(self.elements_analysed)}
            else:
                idx = self.elements_analysed.index(ref)
                return error_data[idx] / total_error * 100 if total_error != 0 else 0
        else:
            _logger.warning("The analysis was not executed. Please run the run_analysis(...) or run_testbench(...)"
                            " before calling this method")
            return None
