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
# Name:        sensitivity_analysis.py
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


class SensitivityAnalysis(ToleranceDeviations):
    """Class to automate Sensitivity simulations"""
    def __init__(self, circuit_file: Union[str, BaseEditor], runner: Optional[AnyRunner] = None):
        super().__init__(circuit_file, runner)
        self.components_analysed = []

    def prepare_testbench(self, **kwargs):
        """Prepares the simulation by setting the tolerances for each component"""
        no = 0
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

