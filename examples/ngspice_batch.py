from spicelib.sim.sim_runner import SimRunner
from spicelib.editor.spice_editor import SpiceEditor
from spicelib.simulators.ngspice_simulator import NGspiceSimulator
from spicelib.utils.sweep_iterators import sweep_log


def processing_data(raw_file, log_file):
    print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))


# select spice model
LTC = SimRunner(output_folder='./temp', simulator=NGspiceSimulator.create_from('C:/Apps/NGSpice64/bin/ngspice.exe'))
netlist = SpiceEditor('./testfiles/testfile_ngspice.net')
# set default arguments
netlist['R1'].value_str = '4k'
netlist['V1'].model = "SINE(0 1 3k 0 0 0)"  # Modifying the behavior of the voltage source
netlist.remove_instruction('.op')
netlist.add_instruction(".tran 1n 3m")
netlist.add_instruction(".plot V(out)")
netlist.add_instruction(".save all")

# .step dec param cap 1p 10u 1
for cap in sweep_log(1e-12, 10e-6, 10):
    netlist['C1'].value = cap
    LTC.run(netlist, callback=processing_data)

LTC.wait_completion()

# Sim Statistics
print('Successful/Total Simulations: ' + str(LTC.okSim) + '/' + str(LTC.runno))
