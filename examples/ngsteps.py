import logging
import spicelib
from spicelib import RawRead, SpiceEditor
from spicelib.simulators.ngspice_simulator import NGspiceSimulator
from matplotlib import pyplot as plt
# set the logger to print to console and at info level
loglevel = logging.INFO
logger = logging.getLogger(__name__)
logging.basicConfig(level=loglevel)
spicelib.set_log_level(loglevel)

netlist_file = "testfiles/ngsteps.net"
raw_file = "testfiles/ngsteps.raw"

# edit the netlist
netlist = SpiceEditor(netlist_file)
# print the netlist
# TODO: get the section, edit the section, save the netlist
print(f"Control sections: {netlist.get_control_sections()}")

print("************************")

i = 0
while i < len(netlist.netlist):
    line = netlist.netlist[i]
    i += 1
    print(f"Line {i}: {line}")

exit()

# run the netlist with ngspice simulator, if present
simulator = NGspiceSimulator
if simulator.is_available():
    # ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -r ngsteps.raw ngsteps.net
    extraparams = simulator.valid_switch("-D", "filetype=ascii")  # binary, or omitting this will work as well.
    ret = simulator.run(netlist_file, cmd_line_switches=extraparams, exe_log=False)
    print(f"NGspice run result: {ret}")

# read the raw file
raw = RawRead(raw_file)
for pl in raw.plots:
    x = pl.get_trace('time')  # Gets the time axis
    y = pl.get_trace('V(out)')
    plt.plot(x.get_wave(), y.get_wave(), label=pl.get_trace_names()[-1])
    
# show the plot
plt.title("NGspice Steps example with control section")
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.grid()
plt.xlim(left=0)  # Start from 0, just looks nicer
plt.legend()
plt.show()

exit()
