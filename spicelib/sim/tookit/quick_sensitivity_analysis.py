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
# Name:        quick_sensitivity_analysis.py
# Purpose:     Classes to make a sensitivity analysis
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-10-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import logging
from typing import Union, Optional, Type, Callable

from .tolerance_deviations import ToleranceDeviations, DeviationType
from ..sim_runner import AnyRunner, ProcessCallback
from ...editor.base_editor import BaseEditor
from ...log.logfile_data import LogfileData

_logger = logging.getLogger("spicelib.SimAnalysis")


class QuickSensitivityAnalysis(ToleranceDeviations):
    """Class to automate Sensitivity simulations"""
    def __init__(self, circuit_file: Union[str, BaseEditor], runner: Optional[AnyRunner] = None):
        super().__init__(circuit_file, runner)
        self.components_analysed = []

    def prepare_testbench(self, **kwargs):
        """Prepares the simulation by setting the tolerances for each component"""
        no = 0
        self.components_analysed.clear()
        use_min = kwargs.get('use_min', False)
        for comp in self.get_components('*'):
            val, dev = self.get_component_value_deviation_type(comp)
            new_val = val
            if dev.typ == DeviationType.tolerance:
                new_val = "{satol(%s,%g,%d)}" % (val, dev.max_val, no)
            elif dev.typ == DeviationType.minmax:
                used_value = dev.min_val if use_min else dev.max_val
                new_val = "{sammx(%s,%g,%d)}" % (val, used_value, no)

            if new_val != val:
                self.set_component_value(comp, new_val)
                self.components_analysed.append(comp)
                no += 1

        self.num_runs = no - 1
        if use_min:
            self.editor.add_instruction(".func satol(nom,tol,idx) nom*if(run==idx,1-tol,1)")
        else:
            self.editor.add_instruction(".func satol(nom,tol,idx) nom*if(run==idx,1+tol,1)")
        self.editor.add_instruction(".func sammx(nom,val,idx) if(run==idx,val,nom)")
        self.editor.add_instruction(".step param run -1 %d 1" % self.num_runs)
        self.editor.set_parameter('run', -1)  # in case the step is commented.
        self.testbench_prepared = True

    def get_sensitivity_data(self, ref: str, measure: str) -> Union[float, dict, None]:
        """
        Returns the sensitivity data for a given component and measurement in terms of percentage of the total error.
        This quick approach is not very accurate, but it is fast. It assumes that the system is linear and that the
        maximum error is the sum of the absolute error of each component. This is a rough approximation, but it is
        good enough for a quick analysis. For more accurate results, use the Worst Case Analysis, which requires
        more simulation runs but gives a more accurate result.
        The best compromise, is to start with the quick analysis and then use the Worst Case Analysis to refine the
        results with only the components that have a significant contribution to the error.
        :param ref: The reference component, or '*' to return a dictionary with all the components
        :param measure: The measurement to be analysed
        :return: The sensitivity data in percentage of the total error for the reference component
        """
        if self.testbench_prepared and self.testbench_executed or self.analysis_executed:
            log_data: LogfileData = self.read_logfiles()
            nominal_data = log_data.get_measure_value(measure, run=-1)
            error_data = []
            for idx, _ in enumerate(self.components_analysed):
                step_data = log_data.get_measure_value(measure, run=idx)
                error_data.append(abs(step_data - nominal_data))
            total_error = sum(error_data)
            if ref == '*':
                return {ref: error_data[idx] / total_error * 100 if total_error != 0 else 0
                        for idx, ref in enumerate(self.components_analysed)}
            else:
                idx = self.components_analysed.index(ref)
                return error_data[idx] / total_error * 100 if total_error != 0 else 0
        else:
            _logger.warning("The analysis was not executed. Please run the run_analysis(...) or run_testbench(...)"
                            " before calling this method")
            return None

    def run_analysis(self,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     ):
        self.clear_simulation_data()
        # Calculate the number of runs

        worst_case_elements = {}
        worst_case_index = []

        def check_and_add_component(ref1: str):
            val1, dev1 = self.get_component_value_deviation_type(ref1)  # get there present value
            if dev1.min_val == dev1.max_val or dev1.typ == DeviationType.none:
                return
            worst_case_elements[ref1] = val1, dev1, 'component'
            worst_case_index.append(ref1)

        for ref in self.device_deviations:
            check_and_add_component(ref)

        for ref in self.parameter_deviations:
            val, dev = self.get_parameter_value_deviation_type(ref)
            if dev.typ == DeviationType.tolerance or dev.typ == DeviationType.minmax:
                worst_case_elements[ref] = val, dev, 'parameter'
                worst_case_index.append(ref)

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    check_and_add_component(ref)

        num_runs = len(worst_case_index)
        if num_runs > 4096:
            _logger.warning("The number of runs is too high. It will be limited to 4096\n"
                            "Consider limiting the number of components with deviation")
            return

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        # Add the run number to the measurements by using a parameter
        self.editor.set_parameter('run', -1)  # in case the step is commented.
        self.editor.add_instruction(".meas run PARAM {run}")
        # Run the simulation in the nominal case
        self.run(self.editor, wait_resource=True,
                 callback=callback, callback_args=callback_args,
                 switches=switches, timeout=timeout)
        last_bit_setting = 0
        for run in range(num_runs):
            # Preparing the variation on components, but only on the ones that have changed
            bit_setting = (2 ** run)
            bit_updated = bit_setting ^ last_bit_setting
            bit_index = 0
            print("bit updated: %d" % bit_updated)
            while bit_updated != 0:
                if bit_updated & 1:
                    ref = worst_case_index[bit_index]
                    val, dev, typ = worst_case_elements[ref]
                    if dev.typ == DeviationType.tolerance:
                        new_val = val * (1 + dev.max_val) if bit_setting & (1 << bit_index) else val
                    elif dev.typ == DeviationType.minmax:
                        new_val = dev.max_val if bit_setting & (1 << bit_index) else val
                    else:
                        _logger.warning("Unknown deviation type")
                        new_val = val
                    if typ == 'component':
                        self.editor.set_component_value(ref, new_val)  # update the value
                    elif typ == 'parameter':
                        self.editor.set_parameter(ref, new_val)
                    else:
                        _logger.warning("Unknown type")
                    print(f"{ref} = {new_val}")
                bit_updated >>= 1
                bit_index += 1
            self.editor.set_parameter('run', run)
            # Run the simulation
            self.run(self.editor, wait_resource=True,
                     callback=callback, callback_args=callback_args,
                     switches=switches, timeout=timeout)
            last_bit_setting = bit_setting
        self.runner.wait_completion()

        if callback is not None:
            callback_rets = []
            for rt in self.simulations:
                callback_rets.append(rt.get_results())
            self.simulation_results['callback_returns'] = callback_rets
        self.analysis_executed = True
