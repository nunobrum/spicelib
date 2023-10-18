from spicelib import AscEditor, SimRunner  # Imports the class that manipulates the asc file
from spicelib.sim.tookit.sensitivity_analysis import SensitivityAnalysis
from spicelib.simulators.ltspice_simulator import LTspice

sallenkey = AscEditor("./testfiles/sallenkey.asc")  # Reads the asc file into memory
runner = SimRunner(simulator=LTspice, output_folder='./temp_wca')  # Instantiates the runner with a temp folder set
sa = SensitivityAnalysis(sallenkey, runner)  # Instantiates the Worst Case Analysis class

# The following lines set the default tolerances for the components
sa.set_tolerance('R', 0.01)  # 1% tolerance
sa.set_tolerance('C', 0.1)  # 10% tolerance
sa.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant

# Some components can have a different tolerance
sa.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well.
sa.set_parameter_deviation('Vos', 3e-4, 5e-3)

sa.remove_instruction("\.AC.*", use_regex=True)  # Removes the .AC instruction
sa.add_instruction(".OP")

# Finally the netlist is saved to a file
sa.save_netlist('./testfiles/temp/sallenkey_sa.asc')


sa.run()  # Runs the simulation with splits of 100 runs each
logs = sa.read_logfiles()   # Reads the log files and stores the results in the results attribute
logs.export_data('./temp_wca/data.csv')  # Exports the data to a csv file

print("Sensitivity results:")


sa.cleanup_files()  # Deletes the temporary files
