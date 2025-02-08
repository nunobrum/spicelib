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
# Purpose:     Class to automate Worst-Case simulations
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from typing import Union, Callable, Type, Dict, Tuple

from .tolerance_deviations import ToleranceDeviations, DeviationType
from ..process_callback import ProcessCallback
from ...log.logfile_data import LogfileData

_logger = logging.getLogger("spicelib.SimAnalysis")


class WorstCaseAnalysis(ToleranceDeviations):
    """
    Class to automate Worst-Case simulations, where all possible combinations of maximum and minimums
    possible values of component values and parameters are done.

    It is advised to use this algorithm when the number of parameters to be varied is reduced.
    Typically less than 10 or 12. A higher number will translate into a huge number of simulations.
    For more than 1000 simulations, it is better to use a statistical method such as the Montecarlo.

    Like the Montecarlo and Sensitivity analysis, there are two possible approaches to use this class:

        1. Preparing a testbench where all combinations are managed directly by the simulator, replacing
         parameters and component values by formulas and using a .STEP primitive to cycle through all possible
         combinations.

        2. Launching each simulation separately where the running python script manages all parameter value
        variations.

    The first approach is normally faster, but not possible in all simulators. The second approach is a valid backup
    when every single simulation takes too long, or when it is prone to crashes and stalls.
    """

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
        self.elements_analysed.clear()
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
            self.elements_analysed.append(ref)

        for prefix in self.default_tolerance:
            for ref in self.get_components(prefix):
                if ref not in self.device_deviations:
                    if self._set_component_deviation(ref, index):
                        index += 1

        self.editor.add_instruction(".func binary(run,idx) {floor(run/(2**idx))-2*floor(run/(2**(idx+1)))}")
        self.editor.add_instruction(".func wc(nom,tol,idx) {if(run<0,nom,nom*(1+tol*(2*binary(run,idx)-1)))}")
        self.editor.add_instruction(".func wc1(nom,min,max,idx) {if(run<0, nom, if(binary(run,idx),max,min))}")
        self.last_run_number = 2**index - 1
        self.editor.add_instruction(".step param run -1 %d 1" % self.last_run_number)
        self.editor.set_parameter('run', -1)  # in case the step is commented.
        self.testbench_prepared = True

    def run_analysis(self,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     exe_log: bool = True,
                     ):
        """This method runs the analysis without updating the netlist.
        It will update component values and parameters according to their deviation type and call the simulation.
        The advantage of this method is that it doesn't require adding random functions to the netlist."""
        self.clear_simulation_data()
        self.elements_analysed.clear()
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

        _logger.info("Worst Case Analysis: %d elements to be analysed", len(self.elements_analysed))

        # Calculate the number of runs
        run_count = 2**len(self.elements_analysed)
        self.last_run_number = run_count - 1

        _logger.info("Worst Case Analysis: %d runs to be executed", run_count)
        if run_count >= 4096:
            _logger.warning("The number of runs is too high. It will be limited to 4096\n"
                            "Consider limiting the number of components with deviation")
            return

        self._reset_netlist()  # reset the netlist
        self.play_instructions()  # play the instructions
        self.editor.set_parameter('run', -1)  # This is aligned with the testbench preparation
        self.editor.add_instruction(".meas runm PARAM {run}")
        # Simulate the nominal case
        self.run(wait_resource=True,
                 callback=callback, callback_args=callback_args,
                 switches=switches, timeout=timeout, exe_log=exe_log)
        self.runner.wait_completion()
        # Simulate the worst case
        last_run = self.last_run_number  # Sets all valid bits to 1
        for run in range(0, run_count):
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
            self.run(wait_resource=True,
                     callback=callback, callback_args=callback_args,
                     switches=switches, timeout=timeout, exe_log=exe_log)
            last_run = run
        self.runner.wait_completion()

        if callback is not None:
            callback_rets = []
            for rt in self.simulations:
                callback_rets.append(rt.get_results())
            self.simulation_results['callback_returns'] = callback_rets
        self.analysis_executed = True

    def get_min_max_measure_value(self, meas_name: str):
        """Returns the minimum and maximum values of a measurement. See SPICE .MEAS primitive documentation."""
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

    def make_sensitivity_analysis(self, measure: str, ref: str = '*') -> Union[Dict[str, Tuple[float, float]],
                                                                               Tuple[float, float], None]:
        """
        Makes a sensitivity analysis for a given measurement and reference component. The sensitivity is a percentage of
        the component error contribution over the total error. As supplement a second value is given that is the
        standard deviation of the error contribution of the component across all sensitivity analysis simulations.

        If no reference is given, it will return a dictionary where the key is the component reference and the value
        is the tuple with (sensitivity, standard_deviation) in percent values of the total error.

        Returns None, if no data still exists for the sensitivity analysis.

        :param measure: measurement name. See SPICE .MEAS primitive
        :type measure: str
        :param ref: Optional component reference in the netlist
        :type ref: str
        :returns: Tuple with sensitivity and a standard deviation or dictionary of tuples.
        """
        if self.testbench_prepared and self.testbench_executed or self.analysis_executed:
            # Read the log files
            log_data: LogfileData = self.read_logfiles()
            wc_data = [log_data.get_measure_value(measure, run=run) for run in range(self.last_run_number + 1)]

            def diff_for_a_ref(wc_data, bit_index):
                """
                Calculates the difference of the measurement for the toggle of a given bit.
                """
                bit_updated = 1 << bit_index
                diffs = []
                for run in range(len(wc_data)):
                    if run & bit_updated == 0:
                        diffs.append(abs(wc_data[run] - wc_data[run | bit_updated]))
                mean = sum(diffs) / len(diffs)
                variance = sum([(diff - mean) ** 2 for diff in diffs]) / len(diffs)
                std_div = variance ** 0.5
                return mean, std_div

            sensitivities = {}
            for ref_ in self.elements_analysed:
                idx = self.elements_analysed.index(ref_)
                sensitivities[ref_] = diff_for_a_ref(wc_data, idx)
            total = sum(sens[0] for sens in sensitivities.values())

            # Calculate the sensitivity for each component if ref is '*'
            # Return the sensitivity as a percentage of the total error
            # This is not very accurate, but it is a way of having
            # sensitivity as a percentages that sum up to 100%.
            if ref == '*':
                # Returns a dictionary with all the references sensitivity
                answer = {}
                for ref, (sens, sigma) in sensitivities.items():
                    answer[ref] = sens / total * 100, sigma / total * 100
                return answer
            else:
                # Calculates the sensitivity for the given component
                sens, sigma = sensitivities[ref]
                return sens /total * 100, sigma / total * 100
        else:
            _logger.warning("The analysis was not executed. Please run the run_analysis(...) or run_testbench(...)"
                            " before calling this method")
            return None
