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
cs = netlist.get_control_sections()
print(f"nr Control sections: {len(cs)}")
s = cs[0]
print(f"Control section 0:\n*********\n{s}\n*********")
# replace the control section with another. Remove/add only, no edit
netlist.remove_control_section(0)  # remove the first control section
s = s.replace(" foreach rval 100 1k 10k", " foreach rval 100 500 1k 5k")
netlist.add_control_section(s)  # add the modified control section back

print("Updates:")
for update in netlist.netlist_updates:
    print(update)
            
netlist_file = "testfiles/temp/ngsteps.net"
netlist.save_netlist(netlist_file)


# run the netlist with ngspice simulator, if present
simulator = NGspiceSimulator
if simulator.is_available():
    raw_file = "testfiles/temp/ngsteps.raw"
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
