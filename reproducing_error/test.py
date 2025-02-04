from spicelib import AscEditor
from spicelib.simulators.ltspice_simulator import LTspice
import subprocess

# AscEditor.set_custom_library_paths("reproducing_error")
#simulator = LTspice
print(LTspice.spice_exe)
print(LTspice.get_default_library_paths())
#AscEditor.prepare_for_simulator(simulator)
#model_fname = "reproducing_error/LPF_3rd.asc"
#netlist = AscEditor(model_fname)
#netlist.save_netlist("reproducing_error/bla.asc")
#model_fname = simulator.create_netlist(model_fname, stderr=subprocess.STDOUT)
#simulator.run(model_fname)
