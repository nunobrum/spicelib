from spicelib import SpiceEditor
from spicelib.simulators.ltspice_simulator import LTspice

LTspice.create_netlist("./testfiles/Noise.asc")
se = SpiceEditor("./testfiles/Noise.net")

se.set_component_value('R1', 11000)
se.set_component_value('C1', 1.1E-6)
se.set_component_value('V1', 11)

se.run(run_filename="./testfiles/Noise_1.net", timeout=10, simulator=LTspice)
