import logging
import spicelib
from spicelib import RawRead, SpiceEditor
from matplotlib import pyplot as plt
# set the logger to print to console and at info level
loglevel = logging.INFO
logger = logging.getLogger(__name__)
logging.basicConfig(level=loglevel)
spicelib.set_log_level(loglevel)

netlist = SpiceEditor("testfiles/ngsteps.net")
# print the netlist
print(f"Netlist: {netlist}")

rawfile = "testfiles/tran_steps_ngspice.ascii.raw"
raw = RawRead(rawfile)

for pl in raw.plots:
    x = pl.get_trace('time')  # Gets the time axis
    y = pl.get_trace('V(out)')
    plt.plot(x.get_wave(), y.get_wave(), label=pl.get_trace_names()[-1])
plt.legend()
plt.show()

exit()

# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -r tran_steps_ngspice.ascii.raw ngsteps.net