from spicelib import SimRunner
from spicelib import AscEditor
from spicelib.simulators.ltspice_simulator import LTspice

# Force another simulatior
simulator = r"C:\Users\nunob\AppData\Local\Programs\ADI\LTspice\LTspice.exe"

# select spice model
runner = SimRunner(output_folder='./temp', simulator=LTspice.create_from(simulator))

netlist = AscEditor('./testfiles/Batch_Test.asc')
# set default arguments
netlist.set_parameters(res=0, cap=100e-6)
netlist['R2'].value = '2k'  # Modifying the value of a resistor
netlist['R1'].value = '4k'
netlist['V3'].value = "SINE(0 1 3k 0 0 0)"

netlist.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
netlist.set_parameter('run', 0)

for opamp in ('AD712', 'AD820'):
    netlist['U1'].model = opamp
    for supply_voltage in (5, 10, 15):
        netlist['V1'].value = supply_voltage
        netlist['V2'].value = -supply_voltage
        print("simulating OpAmp", opamp, "Voltage", supply_voltage)
        runner.run(netlist)

for raw, log in runner:
    print("Raw file: %s, Log file: %s" % (raw, log))
    # do something with the data
    # raw_data = RawRead(raw)
    # log_data = LTSpiceLogReader(log)
    # ...

# Sim Statistics
print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))

enter = input("Press enter to delete created files")
if enter == '':
    runner.file_cleanup()
