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
from typing import Union, Optional

from .tolerance_deviations import ToleranceDeviations, DeviationType
from ..sim_runner import AnyRunner
from ...editor.base_editor import BaseEditor
from ...log.logfile_data import LogfileData


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

    def get_sensitivity_data(self, ref: str, measure: str) -> Union[float, dict]:
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
        if self.testbench_prepared and self.testbench_executed:
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
            raise RuntimeError("Testbench not prepared or executed")

    def run_analysis(self):
        pass