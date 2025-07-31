# coding=utf-8

import sys
sys.path.insert(0, '..')    # This is to allow the import from the spicelib folder
from spicelib import SimRunner, SpiceEditor
from spicelib.sim.process_callback import ProcessCallback  # Importing the ProcessCallback class type


class CallbackProc(ProcessCallback):
    """Class encapsulating the callback function. It can have whatever name."""

    @staticmethod
    def callback(raw_file, log_file):
        print("Handling the simulation data of ""%s"", log file ""%s""" % (raw_file, log_file))
        # Doing some processing here
        return "Parsed Result of ""%s""" % raw_file + ", log file ""%s""" % log_file


if __name__ == "__main__":
    from spicelib.simulators.ltspice_simulator import LTspice
    runner = SimRunner(output_folder='./temp_batch4', simulator=LTspice)  # Configures the simulator to use and output
    # folder

    netlist = SpiceEditor("./testfiles/Batch_Test.net")  # Open the Spice Model, and creates the .net
    # set default arguments
    netlist.set_parameters(res=0, cap=100e-6)
    netlist['R2'].value = '2k'  # Modifying the value of a resistor
    netlist['R1'].value = '4k'
    netlist['V3'].value_str = "SINE(0 1 3k 0 0 0)"  # Modifying the model of a voltage source
    netlist.set_component_value('XU1:C2', 20e-12)  # modifying a component in a subcircuit
    # define simulation
    netlist.add_instructions(
        "; Simulation settings",
        ";.param run = 0"
    )
    netlist.set_parameter('run', 0)

    for opamp in ('AD712', 'AD820'):
        netlist['XU1'].model = opamp
        for supply_voltage in (5, 10, 15):
            netlist['V1'].value = supply_voltage
            netlist['V2'].value = -supply_voltage
            # overriding the automatic netlist naming
            run_netlist_file = "{}_{}_{}.net".format(netlist.netlist_file.stem, opamp, supply_voltage)
            runner.run(netlist, run_filename=run_netlist_file, callback=CallbackProc)

    for result in runner:
        print(result)  # Prints the result of the callback function

    netlist.reset_netlist()
    netlist.remove_Xinstruction(r"\.meas TRAN.*")
    netlist.add_instructions(   # Adding additional instructions
        "; Simulation settings",
        ".ac dec 30 10 1Meg",
        ".meas AC GainAC MAX mag(V(out)) ; find the peak response and call it ""Gain""",
        ".meas AC Fcut TRIG mag(V(out))=GainAC/sqrt(2) FALL=last"
    )

    raw, log = runner.run_now(netlist, run_filename="no_callback.net")
    CallbackProc.callback(raw, log)

    results = runner.wait_completion(1, abort_all_on_timeout=True)

    # Sim Statistics
    print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))


