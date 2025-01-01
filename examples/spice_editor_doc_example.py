# read netlist
import spicelib

net = spicelib.SpiceEditor("./testfiles/Batch_Test.net")  # Loading the Netlist

net.set_parameters(res=0, cap=100e-6)  # Updating parameters res and cap
net['R2'].value = '2k'  # Updating the value of R2 to 2k
net['R1'].value = 4000  # Updating the value of R1 to 4k
net['V3'].model = "SINE(0 1 3k 0 0 0)"  # changing the behaviour of V3

# add instructions
net.add_instructions(
    "; Simulation settings",
    "; .step param run -1 100 1",
)
net.set_parameter('run', -1)
net.save_netlist("Batch_Test_Modified.net")  # writes the modified netlist to the indicated file