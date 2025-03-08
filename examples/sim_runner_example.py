from spicelib import SimRunner
from spicelib import SpiceEditor

from spicelib.simulators.ltspice_simulator import LTspice

# select spice model
runner = SimRunner(simulator=LTspice, output_folder='./temp')
netlist = SpiceEditor('./testfiles/Batch_Test.net')
# set default arguments
netlist.set_parameters(res=0, cap=100e-6)
netlist['R2'].value = '2k'  # Modifying the value of a resistor
netlist.set_component_value('R1', '4k')  # Alternative way of modifying the value of a resistor.
# Set component temperature, Tc 50ppm, remove power rating :
netlist.set_component_parameters('R1', temp=100, tc=0.000050, pwr=None)
netlist['R1'].set_params(temp=100, tc=0.000050, pwr=None)  # Alternative way of setting parameters. Same as the above.
# Modifying the behavior of the voltage source
netlist.set_element_model('V3', "SINE(0 1 3k 0 0 0)")
netlist['V3'].model = "SINE(0 1 3k 0 0 0)"  # Alternative way of modifying the behaviour. Same as the above.
netlist.set_component_value('XU1:C2', 20e-12)  # modifying a component in the subcircuit XU1 instance
netlist.get_subcircuit_named('AD820_ALT')['C13'].value = '2p'  # This changes the value of C13 inside the subcircuit AD820.
# Applies to all instances of the subcircuit
netlist.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
netlist.set_parameter('run', 0)
alt_solver = True
for opamp in ('AD712', 'AD820_ALT_XU1'):  # When updating an instance, the instance name gets appended to the subcircuit
    netlist['XU1'].model = opamp
    # or netlist.set_element_model('XU1', opamp)
    for supply_voltage in (5, 10, 15):
        netlist['V1'].value = supply_voltage
        netlist['V2'].value = -supply_voltage
        print("simulating OpAmp", opamp, "Voltage", supply_voltage)

        # small example on how to use options, here how to force the solver
        opts = []
        if alt_solver:
            opts.append('-alt')
        else:
            opts.append('-norm')

        runner.run(netlist, switches=opts, exe_log=True)  # run, and log console output fo file
        
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
    runner.cleanup_files()
