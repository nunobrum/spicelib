from spicelib.simulators.qspice_simulator import Qspice
from spicelib.sim.simulator import run_function

qpost = [Qspice.spice_exe[0].replace("QSPICE64.exe", "QPOST.exe")]

run_function(qpost, "C:\\Users\\nuno\\Documents\\QSpice\\examples\\test.qraw", "- o C:\\Users\\nuno\\Documents\\QSpice\\examples\\test.meas")
