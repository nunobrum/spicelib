#!/usr/bin/env python
import logging

import spicelib
from spicelib import AscEditor, SimRunner  # Imports the class that manipulates the asc file
from spicelib.sim.tookit.fast_worst_case import FastWorstCaseAnalysis
from spicelib.simulators.ltspice_simulator import LTspice

spicelib.set_log_level(logging.INFO)

sallenkey = AscEditor("./testfiles/sallenkey.asc")  # Reads the asc file into memory
runner = SimRunner(simulator=LTspice, output_folder='./temp_fwca', verbose=True)  # Instantiates the runner with a temp folder set
wca = FastWorstCaseAnalysis(sallenkey, runner)  # Instantiates the Worst Case Analysis class

# The following lines set the default tolerances for the components
wca.set_tolerance('R', 0.01)  # 1% tolerance
wca.set_tolerance('C', 0.1)  # 10% tolerance
# wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant
wca.set_tolerance('I', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant
# Some components can have a different tolerance
wca.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1
wca.set_tolerance('R4', 0.0)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well.
# wca.set_parameter_deviation('Vos', 3e-4, 5e-3)

# Finally the netlist is saved to a file
wca.save_netlist('./testfiles/sallenkey_fwc.asc')

print("=====================================")
# Now using the second method, where the simulations are ran one by one
wca.clear_simulation_data()  # Clears the simulation data
wca.reset_netlist()  # Resets the netlist to the original
nominal, min_value, max_comp_values, max_value, min_comp_values = wca.run_analysis(measure='fcut')  # Makes the Worst Case Analysis
print("Nominal Value", nominal)
print("Worst Case Min", min_value)
print("Min Component Values")
for comp, value in min_comp_values.items():
    print(f"    {comp} = {value}")
print("Worst Case Max", max_value)
print("Max Component Values")
for comp, value in max_comp_values.items():
    print(f"    {comp} = {value}")
wca.cleanup_files()  # Deletes the temporary files
