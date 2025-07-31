# coding=utf-8
import logging

try:
    from rich.logging import RichHandler
except ImportError:
    RichHandler = None

import spicelib

from spicelib import SimRunner, SpiceEditor
from time import sleep
from random import random

spicelib.set_log_level(logging.DEBUG)
if RichHandler is not None:
    spicelib.add_log_handler(RichHandler())


from spicelib.simulators.ltspice_simulator import LTspice


def processing_data(raw_file, log_file, supply_voltage, opamp):
    print("Handling the simulation data of ""%s"", log file ""%s""" % (raw_file, log_file))
    print("Supply Voltage: %s, OpAmp: %s" % (supply_voltage, opamp))
    time_to_sleep = random() * 5
    print(f"Sleeping for {time_to_sleep} seconds")
    sleep(time_to_sleep)
    return "This is the result passed to the iterator"


runner = SimRunner(simulator=LTspice, output_folder='./temp_batch3')  # Configures the simulator to use and output
# folder

netlist = SpiceEditor("./testfiles/Batch_Test.net")  # Open the Spice Model, and creates the .net
# set default arguments
netlist.set_parameters(res=0, cap=100e-6)
netlist['R2'].value = '2k'  # Modifying the value of a resistor
netlist['R1'].value = '4k'
netlist['V3'].value_str = "SINE(0 1 3k 0 0 0)"  # Modifying the model of a voltage source
netlist.set_component_value('XU1:C2', 20e-12)  # modifying a component in a subcircuit
# define simulation
netlist.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
netlist.set_parameter('run', 0)

use_run_now = False

for opamp in ('AD712', 'AD820'):
    netlist['XU1'].model = opamp
    for supply_voltage in (5, 10, 15):
        netlist['V1'].value = supply_voltage
        netlist['V2'].value = -supply_voltage
        # overriding the automatic netlist naming
        run_netlist_file = "{}_{}_{}.net".format(netlist.netlist_file.stem, opamp, supply_voltage)
        if use_run_now:
            runner.run_now(netlist, run_filename=run_netlist_file)
        else:
            runner.run(netlist, run_filename=run_netlist_file, callback=processing_data,
                       callback_args=(supply_voltage, opamp))

for results in runner:
    print(results)

netlist.reset_netlist()
netlist.remove_Xinstruction(r"\.meas TRAN.*")  # This is now needed because LTspice no longer supports cross
netlist.add_instructions(   # Adding additional instructions
        "; Simulation settings",
        ".ac dec 30 10 1Meg",
        ".meas AC Gain_AC MAX mag(V(out)) ; find the peak response and call it ""Gain""",
        ".meas AC Fcut TRIG mag(V(out))=Gain_AC/sqrt(2) FALL=last"
)

raw, log = runner.run(netlist, run_filename="no_callback.net").wait_results()
processing_data(raw, log, 0, 0)

if use_run_now is False:
    results = runner.wait_completion(1, abort_all_on_timeout=True)

    # Sim Statistics
    print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
