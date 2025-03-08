import os

from spicelib import SpiceEditor, SimRunner
from spicelib.simulators.ltspice_simulator import LTspice
from spicelib.sim.sim_stepping import SimStepper


def processing_data(raw_file, log_file):
    print("Handling the simulation data of %s" % log_file)


runner = SimRunner(parallel_sims=4, output_folder='./temp2', simulator=LTspice)

# select spice model
Stepper = SimStepper(SpiceEditor("./testfiles/Batch_Test.net"), runner)
# set default arguments

Stepper.set_parameters(res=0, cap=100e-6)
Stepper.set_component_value('R2', '2k')
Stepper.set_component_value('R1', '4k')
Stepper.set_element_model('V3', "SINE(0 1 3k 0 0 0)")
# define simulation
Stepper.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
Stepper.set_parameter('run', 0)
Stepper.set_parameter('test_param2', 20)
Stepper.add_model_sweep('XU1', ('AD712', 'AD820_ALT'))
Stepper.add_value_sweep('V1', (5, 10, 15))
# Stepper.add_value_sweep('V1', (-5, -10, -15))

run_netlist_file = "run_OPAMP_{XU1}_VDD_{V1}.net"
Stepper.run_all(callback=processing_data, filenamer=run_netlist_file.format)

# Sim Statistics
print('Successful/Total Simulations: ' + str(Stepper.okSim) + '/' + str(Stepper.runno))
Stepper.export_step_info("./temp2/export.csv")
runner.cleanup_files()
