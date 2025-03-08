#!/usr/bin/env python

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        sim_stepping.py
# Purpose:     Spice Simulation Library intended to automate the exploring of
#              design corners, try different models and different parameter
#              settings.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     31-07-2020
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2017, Fribourg Switzerland"

import pathlib
from typing import Callable, Union, Type, Iterable, Dict, List
from functools import wraps
import logging

from spicelib.sim.process_callback import ProcessCallback

_logger = logging.getLogger("spicelib.SimStepper")
from ..editor.base_editor import BaseEditor
from .sim_runner import AnyRunner


class StepInfo(object):
    def __init__(self, what: str, elem: str, iterable: Iterable):
        self.what = what
        self.elem = elem
        self.iter = iterable

    def __len__(self):
        return len(list(self.iter))

    def __str__(self):
        return f"Iteration on {self.what} {self.elem} : {self.iter}"


class SimStepper(AnyRunner):
    """This class is intended to be used for simulations with many parameter sweeps. This provides a more
    user-friendly interface than the SpiceEditor/SimRunner class when there are many parameters to be stepped.

    Using the SpiceEditor/SimRunner classes a loop needs to be added for each dimension of the simulations.
    A typical usage would be as follows:
    ```
    netlist = SpiceEditor("my_circuit.asc")
    runner = SimRunner(parallel_sims=4)
    for dmodel in ("BAT54", "BAT46WJ")
        netlist.set_element_model("D1", model)  # Sets the Diode D1 model
        for res_value1 in sweep(2.2, 2,4, 0.2):  # Steps from 2.2 to 2.4 with 0.2 increments
            netlist.set_component_value('R1', res_value1)  # Updates the resistor R1 value to be 3.3k
            for temperature in sweep(0, 80, 20):  # Makes temperature step from 0 to 80 degrees in 20 degree steps
                netlist.set_parameters(temp=80)  # Sets the simulation temperature to be 80 degrees
                for res_value2 in (10, 25, 32):
                    netlist.set_component_value('R2', res_value2)  # Updates the resistor R2 value to be 3.3k
                    runner.run(netlist)

    runner.wait_completion()  # Waits for the Spice simulations to complete
    ```

    With SimStepper the same thing can be done as follows, resulting in a cleaner code.

    ```
    netlist = SpiceEditor("my_circuit.asc")
    Stepper = SimStepper(netlist, SimRunner(parallel_sims=4, output_folder="./output"))
    Stepper.add_model_sweep('D1', "BAT54", "BAT46WJ")
    Stepper.add_component_sweep('R1', sweep(2.2, 2,4, 0.2))  # Steps from 2.2 to 2.4 with 0.2 increments
    Stepper.add_parameter_sweep('temp', sweep(0, 80, 20))  # Makes temperature step from 0 to 80 degrees in 20
                                                           # degree steps
    Stepper.add_component_sweep('R2', (10, 25, 32)) #  Updates the resistor R2 value to be 3.3k
    Stepper.run_all()

    ```

    Another advantage of using SimStepper is that it can optionally use the .SAVEBIAS in the first simulation and
    then use the .LOADBIAS command at the subsequent ones to speed up the simulation times.
    """

    def __init__(self, circuit: BaseEditor, runner: AnyRunner):
        self.runner = runner
        self.netlist = circuit
        self.iter_list: List[StepInfo] = []
        self.current_values = {}
        self.sim_info = {}

    @wraps(BaseEditor.add_instruction)
    def add_instruction(self, instruction: str):
        self.netlist.add_instruction(instruction)

    @wraps(BaseEditor.add_instructions)
    def add_instructions(self, *instructions) -> None:
        self.netlist.add_instructions(*instructions)

    @wraps(BaseEditor.remove_instruction)
    def remove_instruction(self, instruction) -> None:
        self.netlist.remove_instruction(instruction)

    @wraps(BaseEditor.remove_Xinstruction)
    def remove_Xinstruction(self, search_pattern) -> None:
        self.netlist.remove_Xinstruction(search_pattern)

    @wraps(BaseEditor.set_parameters)
    def set_parameters(self, **kwargs):
        self.netlist.set_parameters(**kwargs)
        self.current_values.update(**kwargs)

    @wraps(BaseEditor.set_parameter)
    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        self.netlist.set_parameter(param, value)
        self.current_values[param] = value

    @wraps(BaseEditor.set_component_values)
    def set_component_values(self, **kwargs):
        self.netlist.set_component_values(**kwargs)
        self.current_values.update(**kwargs)

    @wraps(BaseEditor.set_component_value)
    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        self.netlist.set_component_value(device, value)
        self.current_values[device] = value

    @wraps(BaseEditor.set_element_model)
    def set_element_model(self, element: str, model: str) -> None:
        self.netlist.set_element_model(element, model)
        self.current_values[element] = model

    def add_param_sweep(self, param: str, iterable: Iterable):
        """Adds a dimension to the simulation, where the param is swept."""
        self.iter_list.append(StepInfo("param", param, iterable))

    def add_value_sweep(self, comp: str, iterable: Iterable):
        """Adds a dimension to the simulation, where a component value is swept."""
        # The next line raises an ComponentNotFoundError if the component doesn't exist
        _ = self.netlist.get_component_value(comp)
        self.iter_list.append(StepInfo("component", comp, iterable))

    def add_model_sweep(self, comp: str, iterable: Iterable):
        """Adds a dimension to the simulation, where a component model is swept."""
        # The next line raises an ComponentNotFoundError if the component doesn't exist
        _ = self.netlist.get_component_value(comp)
        self.iter_list.append(StepInfo("model", comp, iterable))

    def total_number_of_simulations(self):
        """Returns the total number of simulations foreseen."""
        total = 1
        for step in self.iter_list:
            l = len(step)
            if l:
                total *= l
            else:
                _logger.debug(f"'{step}' is empty.")
        return total

    def run_all(self,
                callback: Union[Type[ProcessCallback], Callable] = None,
                callback_args: Union[tuple, dict] = None,
                switches=None,
                timeout: float = None,
                wait_completion: bool = True,
                filenamer: Callable[[Dict[str, str]], str] = None,
                exe_log: bool = False,
                ) -> None:
        """
        Runs all sweeps configured with the methods:

            - add_value_sweep()
            - add_model_sweep()
            - add_param_sweep()

        This function will call the SimRunner run method for each combination of the sweeps defined.
        The parameters are mostly the same as in the SimRunner.run() method, except the filenamer and
        wait_completion parameters.

        :param callback: See the SimRunner run method.
        :type: callback: function(raw_file: Path, log_file: Path, ...), optional
        :param callback_args: See the SimRunner run method.
        :type callback_args: dict or tuple, optional
        :param switches: Command line switches override
        :type switches: list
        :param timeout: See the SimRunner run method.
        :type timeout: float, optional
        :param wait_completion:  See the SimRunner run method.
        :type wait_completion: bool, optional
        :param filenamer:
            A function that receives a dictionary in keyword form (**dict) and returns a string. This string will be
            passed to the run_filename parameter on the SimRunner run method. It is important that the function assures
            a unique filename per simulation.
        :type filenamer: Callable receiving keyword parameters.
        :param exe_log: See the SimRunner run method.
        :type exe_log: bool, optional
        :returns: Nothing
        """
        iter_no = 0
        iterators = [iter(step.iter) for step in self.iter_list]
        while True:
            while 0 <= iter_no < len(self.iter_list):
                try:
                    value = iterators[iter_no].__next__()
                except StopIteration:
                    iterators[iter_no] = iter(self.iter_list[iter_no].iter)
                    iter_no -= 1
                    continue

                self.current_values[self.iter_list[iter_no].elem] = value
                if self.iter_list[iter_no].what == 'param':
                    self.netlist.set_parameter(self.iter_list[iter_no].elem, value)
                elif self.iter_list[iter_no].what == 'component':
                    self.netlist.set_component_value(self.iter_list[iter_no].elem, value)
                elif self.iter_list[iter_no].what == 'model':
                    self.netlist.set_element_model(self.iter_list[iter_no].elem, value)
                else:
                    # TODO: develop other types of sweeps EX: add .STEP instruction
                    raise ValueError("Not Supported sweep")
                iter_no += 1
            if iter_no < 0:
                break

            run_filename = filenamer(**self.current_values) if filenamer else None

            task = self.runner.run(self.netlist, callback=callback, callback_args=callback_args,
                                   switches=switches, timeout=timeout, run_filename=run_filename, exe_log=exe_log)

            # Now storing the simulation information
            if task and task.netlist_file:
                sim_info = self.current_values.copy()
                sim_info['netlist'] = task.netlist_file.name
                self.sim_info[task.runno] = sim_info

            iter_no = len(self.iter_list) - 1  # Resets the counter to start next iteration
        if wait_completion:
            # Now waits for the simulations to end
            self.runner.wait_completion()

    def export_step_info(self, export_filename: Union[pathlib.Path, str], delimiter: str = ";"):
        """
        Exports the stepping values to a CSV file. It writes a row per each simulation done.
        The columns are all the values that were set during the session. The value on each row is the value
        of the parameter or component value/model at each simulation.
        This information can also be accessed using the sim_info attribute. The sim_info contains a di

        :param export_filename: export file path
        :type export_filename: str or pathlib.Path
        :param delimiter: delimiter character on the CSV
        :type delimiter: str
        """
        import csv

        rows = [runno for runno in self.sim_info]
        rows.sort()

        # Extract column names from the first dictionary
        fieldnames = ['runno'] + list(self.sim_info[rows[0]].keys())

        # Open a CSV file for writing
        with open(export_filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=delimiter,
                                    quotechar='"', quoting=csv.QUOTE_NONNUMERIC)

            # Write the header
            writer.writeheader()

            # Write the data
            for runno in rows:
                row_data_with_id = {'runno': runno}
                row_data_with_id.update(self.sim_info[runno])
                writer.writerow(row_data_with_id)

    # def run(self, netlist: Union[str, pathlib.Path, BaseEditor], *,
    #         wait_resource: bool = True,
    #         callback: Union[Type[ProcessCallback], Callable] = None,
    #         callback_args: Union[tuple, dict] = None,
    #         switches=None,
    #         timeout: float = None,
    #         run_filename: str = None,
    #         exe_log: bool = False) -> Union[RunTask, None]:
    #     """Rather uses run_all instead"""
    #     self.run_all()

    @property
    def okSim(self):
        """Number of successful simulations"""
        return self.runner.okSim

    @property
    def runno(self):
        """Number simulations done."""
        return self.runner.runno

    @property
    def failSim(self):
        """Number of failed simulations"""
        return self.runner.failSim
