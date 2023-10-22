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

import logging
import random
from typing import Union, Callable, Type

_logger = logging.getLogger("spicelib.SimAnalysis")

from .tolerance_deviations import ToleranceDeviations, DeviationType, ComponentDeviation
from ..process_callback import ProcessCallback
from ...log.logfile_data import LogfileData



class Montecarlo(ToleranceDeviations):
    """Class to automate Monte-Carlo simulations"""

    def prepare_testbench(self, **kwargs):
        """
        Prepares the simulation by setting the tolerances for the components
        :keyword num_runs: Number of runs to be performed. Default is 1000.
        :return: None
        """
        min_max_uni_func = False
        min_max_norm_func = False
        tol_uni_func = False
        tol_norm_func = False
        for ref in self.get_components('*'):
            val, dev = self.get_component_value_deviation_type(ref)  # get there present value
            new_val = val
            if dev.typ == DeviationType.tolerance:
                tolstr = ('%g' % dev.max_val).rstrip('0').rstrip('.')
                if dev.distribution == 'uniform':
                    new_val = "{utol(%s,%s)}" % (val, tolstr)  # calculate expression for new value
                    tol_uni_func = True
                elif dev.distribution == 'normal':
                    new_val = "{ntol(%s,%s)}" % (val, tolstr)
                    tol_norm_func = True
            elif dev.typ == DeviationType.minmax:
                if dev.distribution == 'uniform':
                    new_val = "{urng(%s, %s,%s)}" % (val, dev.min_val, dev.max_val)  # calculate expression for new value
                    min_max_uni_func = True
                elif dev.distribution == 'normal':
                    new_val = "{nrng(%s,%s,%s)}" % (val, dev.min_val, dev.max_val)
                    min_max_norm_func = True

            if new_val != val:  # Only update the value if it has changed
                self.set_component_value(ref, new_val)  # update the value

        for param in self.parameter_deviations:
            val, dev = self.get_parameter_value_deviation_type(param)
            new_val = val
            if dev.typ == DeviationType.tolerance:
                if dev.distribution == 'uniform':
                    new_val = "{utol(%s,%g)}" % (val, dev.max_val)
                    tol_uni_func = True
                elif dev.distribution == 'normal':
                    new_val = "{ntol(%g,%g)}" % (val, dev.max_val)
                    tol_norm_func = True
            elif dev.typ == DeviationType.minmax:
                if dev.distribution == 'uniform':
                    new_val = "{urng(%s,%g,%g)}" % (val, (dev.max_val+dev.min_val)/2, (dev.max_val-dev.min_val)/2)
                    min_max_uni_func = True
                elif dev.distribution == 'normal':
                    new_val = "{nrng(%s,%g,%g)}" % (val, (dev.max_val+dev.min_val)/2, (dev.max_val-dev.min_val)/6)
                    min_max_norm_func = True
            else:
                continue
            self.editor.set_parameter(param, new_val)

        if tol_uni_func:
            self.editor.add_instruction(".func utol(nom,tol) if(run<0, nom, mc(nom,tol))")

        if tol_norm_func:
            self.editor.add_instruction(".func ntol(nom,tol) if(run<0, nom, nom*(1+gauss(tol/3)))")

        if min_max_uni_func:
            self.editor.add_instruction(".func urng(nom,mean,df2) if(run<0, nom, mean*flat(df2))")

        if min_max_norm_func:
            self.editor.add_instruction(".func nrng(nom,mean,df6) if(run<0, nom, mean*(1+gauss(df6)))")

        self.num_runs = kwargs.get('num_runs', self.num_runs if self.num_runs != 0 else 1000)
        self.editor.add_instruction(".step param run -1 %d 1" % self.num_runs)
        self.editor.set_parameter('run', -1)
        self.testbench_prepared = True

    def _get_sim_value(self, value: float, dev: ComponentDeviation) -> float:
        """Returns a new value for the simulation"""
        new_val = value
        if dev.typ == DeviationType.tolerance:
            if dev.distribution == 'uniform':
                new_val = f"{random.Random().uniform(value * (1- dev.max_val), value * (1 + dev.max_val)):g}"
            elif dev.distribution == 'normal':
                new_val = f"{random.Random().gauss(value, dev.max_val / 3):g}"
        elif dev.typ == DeviationType.minmax:
            if dev.distribution == 'uniform':
                new_val = f"{random.Random().uniform(dev.min_val, dev.max_val):g}"
            elif dev.distribution == 'normal':
                new_val = f"{random.Random().gauss((dev.max_val + dev.min_val) / 2, (dev.max_val - dev.min_val) / 6):g}"
        else:
            _logger.warning("Unknown deviation type")
        return new_val

    def run_analysis(self, num_runs: int = 1000,
                     callback: Union[Type[ProcessCallback], Callable] = None,
                     callback_args: Union[tuple, dict] = None,
                     switches=None,
                     timeout: float = None,
                     ):
        """This method runs the analysis without updating the netlist.
        It will update component values and parameters according to their deviation type and call the simulation.
        The advantage of this method is that it doesn't require adding random functions to the netlist.
        The number of times the simulation is done is specified on the argument num_runs."""
        self.clear_simulation_data()
        for run in range(num_runs):
            self._reset_netlist() # reset the netlist
            self.play_instructions() # play the instructions
            # Preparing the variation on components
            for ref in self.get_components('*'):
                val, dev = self.get_component_value_deviation_type(ref)  # get there present value
                new_val = self._get_sim_value(val, dev)
                if new_val != val:  # Only update the value if it has changed
                    self.editor.set_component_value(ref, new_val)  # update the value
            # Preparing the variation on parameters
            for param in self.parameter_deviations:
                val, dev = self.get_parameter_value_deviation_type(param)
                new_val = self._get_sim_value(val, dev)
                if new_val != val:  # Only update the value if it has changed
                    self.editor.set_parameter(param, new_val)
            # Run the simulation
            rt = self.run(self.editor, wait_resource=True,
                          callback=callback, callback_args=callback_args,
                          switches=switches, timeout=timeout)

        self.runner.wait_completion()
        if callback is not None:
            callback_rets = []
            for rt in self.simulations:
                callback_rets.append(rt.get_results())
            self.simulation_results['callback_returns'] = callback_rets
        self.analysis_executed = True

    def analyse_measurement(self, meas_name: str):
        """Returns the measurement data for the given measurement name.
        If the measurement is not found, it returns None
        Note: It is up to the user to make the statistics on the data. The traditional way is to use the numpy package
        to calculate the mean and standard deviation of the data. It is also usual to consider max and min as 3 sigma,
        which is 99.7% of the data.
        """
        if not self.analysis_executed:
            _logger.warning("The analysis was not executed. Please run the analysis before calling this method")
            return None
        log_data: LogfileData = self.read_logfiles()
        meas_data = log_data[meas_name]
        if meas_data is None:
            _logger.warning("Measurement %s not found in log files", meas_name)
            return None
        else:
            return meas_data
