# README #

spicelib is a toolchain of python utilities design to interact with spice simulators, as for example:

* LTspice
* Ngspice
* QSPICE
* Xyce

## What is contained in this repository ##

### Main Tools ###

* __Analysis Toolkit__
  A set of tools that prepare an LTspice netlist for a Montecarlo or Worst Case Analysis. The device tolerances are set by the user and the netlist is updated accordingly. The netlist can then be used with the SimRunner to run a batch of simulations or with the LTspice GUI.

* __ltsteps.py__
  An utility that extracts from LTspice output files data, and formats it for import in a spreadsheet, such like Excel or Calc.

* __histogram.py__
  A python script that uses numpy and matplotlib to create a histogram and calculate the sigma deviations. This is useful for Monte-Carlo analysis.


### Main Classes ###

* __AscEditor/QschEditor/SpiceEditor__
  Classes for the manipulation of respectively:

  * LTspice `.asc` files
  * QSPICE `.qsch` files
  * SPICE netlists (from no matter what simulator)
  
  without having to open the schematic in a GUI. The simulations can then be run in batch mode (see SimRunner). Examples of functions provided:

  * `netlist.set_element_model('D1', '1N4148') # Replaces the Diode D1 with the model 1N4148`
  * `netlist.set_component_value('R2', '33k') # Replaces the value of R2 by 33k`
  * `netlist['R2'].value = 33000 # Same as above`
  * `netlist.set_component_value('V1', '5') # Replaces the value of V1 by 5`
  * `netlist['V1'].value = 5 # Same as above`
  * `netlist.set_parameters(run=1, TEMP=80) # Creates or updates the netlist to have .PARAM run=1 or .PARAM TEMP=80`
  * `netlist.add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")`
  * `netlist.remove_instruction(".STEP run -1 1023 1")  # Removes previously added instruction`
  * `netlist.reset_netlist() # Resets all edits done to the netlist.`
  * `netlist.set_component_parameters('R1', temp=25, pwr=None)  # Sets or removes additional parameters`

* __SimRunner__
  A class that can be used to run LTspice/QSPICE/Ngspice/Xyce simulations in batch mode without having to open the corresponding GUI.
  This, in cooperation with the above mentioned xxxEditor classes, is useful because:

  * It can overcome the limitation of only stepping 3 parameters
  * Different types of simulations .TRAN .AC .NOISE can be run in a single batch
  * The RAW Files are smaller and easier to handle
  * When used with RawRead and ltsteps.py, validation of the circuit can be done automatically
  * Different models can be simulated in a single batch

* __RawRead__
  A class that serves to read raw files into a python class.

* __RawWrite__
  A class to write RAW files that can be read by the LTspice Wave Application.

## How to Install ##

`pip install spicelib`

### Updating spicelib ###

`pip install --upgrade spicelib`

### Using GITHub ###

`git clone https://github.com/nunobrum/spicelib.git`

If using this method it would be good to add the path where you cloned the site to python path.

`import sys`  
`sys.path.append(<path to spicelib>)`

## How to use ##

Here follows a quick outlook on how to use each of the tools.

More comprehensive documentation can be found in <https://spicelib.readthedocs.io/en/latest/>

## LICENSE ##

GNU V3 License
(refer to the LICENSE file)

## Main modules ##

### RawRead ###

The example below reads the data from a Spice Simulation called
"TRAN - STEP.raw" and displays all steps of the "I(R1)" trace in a matplotlib plot

 ```python
from spicelib import RawRead

from matplotlib import pyplot as plt

rawfile = RawRead("./testfiles/TRAN - STEP.raw")

print(rawfile.get_trace_names())
print(rawfile.get_raw_property())

IR1 = rawfile.get_trace("I(R1)")
x = rawfile.get_trace('time')  # Gets the time axis
steps = rawfile.get_steps()
for step in range(len(steps)):
    # print(steps[step])
    plt.plot(x.get_wave(step), IR1.get_wave(step), label=steps[step])

plt.legend()  # order a legend
plt.show()
 ```

-- in examples/raw_read_example.py

### RawWrite ###

The following example writes a RAW file with a 3 milliseconds transient simulation sine with a 10kHz and a cosine with
9.997kHz

 ```python
import numpy as np
from spicelib import Trace, RawWrite
LW = RawWrite(fastacces=False)
tx = Trace('time', np.arange(0.0, 3e-3, 997E-11))
vy = Trace('N001', np.sin(2 * np.pi * tx.data * 10000))
vz = Trace('N002', np.cos(2 * np.pi * tx.data * 9970))
LW.add_trace(tx)
LW.add_trace(vy)
LW.add_trace(vz)
LW.save("./testfiles/teste_snippet1.raw")
 ```

-- in examples/raw_write_example.py [Example 1]

### SpiceEditor, AscEditor, QschEditor and SimRunner ###

These modules are used to prepare and launch SPICE simulations.

The editors can be used change component values, parameters or simulation commands. After the simulation is run, the results then can be processed with either the RawRead or with the LTSpiceLogReader module to read the log file which can contain .MEAS results.

Here follows an example of operation.

```python
from spicelib import SimRunner
from spicelib import SpiceEditor

from spicelib.simulators.ltspice_simulator import LTspice

# select spice model
LTC = SimRunner(simulator=LTspice, output_folder='./temp')
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
netlist['XU1:C2'].value = 20e-12  # modifying a define simulation
netlist.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
netlist.set_parameter('run', 0)
alt_solver = True
for opamp in ('AD712', 'AD820'):
    netlist['XU1'].model = opamp
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

        LTC.run(netlist, opts)

for raw, log in LTC:
    print("Raw file: %s, Log file: %s" % (raw, log))
    # do something with the data
    # raw_data = RawRead(raw)
    # log_data = LTSpiceLogReader(log)
    # ...

netlist.reset_netlist()
netlist.add_instructions(
    "; Simulation settings",
    ".ac dec 30 10 1Meg",
    ".meas AC Gain MAX mag(V(out)) ; find the peak response and call it ""Gain""",
    ".meas AC Fcut TRIG mag(V(out))=Gain/sqrt(2) FALL=last"
)

# Sim Statistics
print('Successful/Total Simulations: ' + str(LTC.okSim) + '/' + str(LTC.runno))

enter = input("Press enter to delete created files")
if enter == '':
    LTC.file_cleanup()
```

-- in examples/sim_runner_example.py

The example above is using the SpiceEditor to modify a spice netlist, but it is also possible to use the AscEditor to directly modify a .asc file. The edited .asc file can be opened by the LTspice GUI and the simulation can be run from there. It is also possible to open a .asc file and to generate a spice netlist from it.

#### Simulators and Windows, Linux and MacOS compatibility ####

The **LTspice** class tries to detect the correct path of the LTspice installation depending on the platform. On Linux it expects LTspice to be installed under wine. On MacOS, it first looks for LTspice installed under wine, and when it cannot be found, it will look for native LTspice. The reason is that the command line interface of the native LTspice is severely limited.

**Ngspice** runs natively under Windows, Linux and MacOS (via brew). This library works with Ngspice CLI, and tries to detect the correct executable path, no matter the platform. It cannot (yet) work with the shared library version of Ngspice that is delivered with for example Kicad, you will need to install the CLI version. You can however use Kicad as the schema editor and subsequently save the Ngspice netlist to use it with this library.

For the other simulators, built-in Linux/MacOS support is coming, but you can always try to use it under Linux via setting of the executable paths.

#### Executable and Library paths ####

A large variety of standard paths are automatically detected. To see what paths are detected:

```python
runner = SimRunner(output_folder='./tmp', simulator=LTspice)
# Show the executable path
print(runner.simulator.spice_exe)
print(runner.simulator.process_name)
# Show the default library paths of that simulator. This is deduced from `spice_exe`
print(runner.simulator.get_default_library_paths())
```

If you want, you can set your own **executable paths**, via the two variables shown above:

* `spice_exe`: a list of with the commands that invoke the sumulator. Do not include command line options to the simulator here.
* `process_name`: the process name as visible to the OS.

You can also use `simulator.create_from()`.

The **library paths** are needed for the editors. However, the default library paths depend on the simulator used, its installation path, and if that simulator runs under wine or not. The function `editor.prepare_for_simulator()` allows you to tell the editor what simulator is used, and its library paths. This not always needed however:

* `AscEditor` and `SpiceEditor` presume that LTspice is used.
* `QschEditor` presumes that QSPICE is used.

 This will of course not work out if you use the editors on other simulators (as can be the case with `SpiceEditor`), or if you have manually set the simulator's executable path. In those cases you will want to inform your editor of that change via `editor.prepare_for_simulator()`.

If you want, you can also add extra library search paths via `editor.set_custom_library_paths()`.

**Example**:

```python
# ** Simulator executable paths

# OPTION 1: via subclassing
class MySpiceInstallation(LTspice):
    spice_exe = ['wine', '/custompath/LTspice.exe']
    process_name = 'wine'

runner = SimRunner(output_folder='./tmp', simulator=MySpiceInstallation)

# OPTION 2: or via direct creation. If you do not specify the process_name,
# it will be guessed via `simulator.guess_process_name()`.
runner = SimRunner(output_folder='./tmp', 
                   simulator=LTspice.create_from('wine /custompath/LTspice.exe')
                  )

# ** Editor library paths

# In case of non standard paths, or a change of the default simulator, it is preferred to
# inform your editor of it, so it can better guess the library paths. 
AscEditor.prepare_for_simulator(MySpiceInstallation)

# You can also add your own library paths to the search paths
AscEditor.set_custom_library_paths(["/mypath/lib/sub",
                                    "/mypath/lib/sym",
                                    "/mypath/lib/sym/OpAmps",
                                    "/mypath/lib/cmp"])

```

#### Runner log redirection ####

When you use wine (on Linux or MacOS) or a simulator like Ngspice, you may want to redirect the output of `run()`, as it prints a lot of messages without much value. Real time redirecting to the logger is unfortunately not easy. You can redirect the output for example with:

```python
# force command output to a separate file
with open(processlogfile, "w") as outfile:
    runner.run(netlist, timeout=None, stdout=outfile, stderr=subprocess.STDOUT)
```

#### Limitations and specifics of AscEditor ####

AscEditor has some limitations and differences with regards to SpiceEditor.

* As is visible in the LTspice GUI, it groups all component properties/parameters in different 'attributes' like 'Value', 'Value2', 'SpiceLine', 'SpiceLine2'. Netlists do not have that concept, and place everything in one big list, that SpiceEditor subsequently separates in 'value' and 'parameters' for most components. To complicate things, LTspice distributes the parameters over all 4 attributes, with varying syntax. You must be aware of how LTspice handles the parameter placement if you use AscEditor.
  
  `AscEditor.get_component_parameters()` will show the native attributes, and tries to disect 'SpiceLine' and 'SpiceLine2', just like `SpiceEditor.get_component_parameters()` would do.
  This means for example for a Voltage source of DC 2V, with small signal analysis AC amplitude of 1V and a series resistance of 3 ohm:
  * `AscEditor.get_component_value()` and `SpiceEditor.get_component_value()` -> `'2 AC 1'`
  * `AscEditor.get_component_parameters()` -> `{'Value': '2', 'Value2': 'AC 1', 'SpiceLine': 'Rser=3', 'Rser': 3}`
  * `SpiceEditor.get_component_parameters()` -> `{'Rser': 3}`
  * Please note that if you want to remove the small signal analysis AC amplitude, you MUST use
    * `AscEditor.set_component_parameters(..,'Value2','')`, as `set_component_value()` will only affect 'Value'
    * `SpiceEditor.set_component_value(..,'2')`
  * with both editors, you can use `...set_component_parameters(.., Rser=5)`
* When adressing components, SpiceEditor requires you to include the prefix in the component name, like `XU1` for an opamp. AscEditor will require `U1`.
* AscEditor and SpiceEditor only work with the information in their respective schema/circuit files. The problem is that LTspice does not store any of the underlying symbol's default parameter values in the .asc files. SpiceEditor works on netlists, and netlists do contain all parameters.

    This can affect the behaviour when using symbols like `OpAmps/UniversalOpAmp2`. Although the LTspice GUI shows the parameters like `Avol`, `GBW` and `Vos`, even when they have the default values, `AscEditor.get_component_parameters()` will not return these parameters unless they have been modified. `SpiceEditor.get_component_parameters()` on the contrary will show all parameters, regardless of if they were modified. It is however possible for AscEditor to set or modify the parameters with `AscEditor.set_component_parameters()`. Example:  `set_component_parameters("U1", Value2="Avol=2Meg GBW=10Meg Slew=10Meg")`. 

    Note here that you must know the correct attribute holding that parameter, and make sure that you know and set all the other parameters in that attribute. If the attribute is in 'SpiceLine' however (as with the majority of the simpler components), you may address the parameter individually (see the voltage source example above).

Resumed, it is better to use SpiceEditor than AscEditor, as it is more straightforward. On MacOS, it is recommended to use LTspice under wine, or to export the netlist manually, as MacOS's LTspice does not support automated export of netlists.

### Simulation Analysis Toolkit ###

The AscEditor can be used with the Simulation Analysis Toolkit to perform Monte Carlo or Wost Case simulations.
These simulations can either be done on the LTSpice GUI or using the Runner Class described above.

Let's consider the following circuit:

![Sallen-Key Amplifier](./doc/modules/sallenkey.png "Sallen-Key Amplifier")

When performing a Monte Carlo simulation on this circuit, we need to manually modify the value of each component,
and then add the .step command for making several runs on the same circuit.
To simplify this process, the AscEditor class can be used as exemplified below:

```python
from spicelib import AscEditor, SimRunner  # Imports the class that manipulates the asc file
from spicelib.sim.tookit.montecarlo import Montecarlo  # Imports the Montecarlo toolkit class
from spicelib.simulators.ltspice_simulator import LTspice

sallenkey = AscEditor("./testfiles/sallenkey.asc")  # Reads the asc file into memory
runner = SimRunner(simulator=LTspice, output_folder='./temp_mc',
                   verbose=True)  # Instantiates the runner with a temp folder set
mc = Montecarlo(sallenkey, runner)  # Instantiates the Montecarlo class, with the asc file already in memory

# The following lines set the default tolerances for the components
mc.set_tolerance('R', 0.01)  # 1% tolerance, default distribution is uniform
mc.set_tolerance('C', 0.1, distribution='uniform')  # 10% tolerance, explicit uniform distribution
mc.set_tolerance('V', 0.1, distribution='normal')  # 10% tolerance, but using a normal distribution

# Some components can have a different tolerance
mc.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well
mc.set_parameter_deviation('Vos', 3e-4, 5e-3, 'uniform')  # The keyword 'distribution' is optional
mc.prepare_testbench(num_runs=1000)  # Prepares the testbench for 1000 simulations

# Finally the netlist is saved to a file. This file contians all the instructions to run the simulation in LTspice
mc.save_netlist('./testfiles/temp/sallenkey_mc.asc')
```

-- in examples/run_montecarlo.py [Example 1]

When opening the created sallenkey_mc.net file, we can see that the following circuit.

![Sallen-Key Amplifier with Montecarlo](./doc/modules/sallenkey_mc.png "Sallen-Key Amplifier with Montecarlo")

The following updates were made to the circuit:

* The value of each component was replaced by a function that generates a random value within the specified tolerance.
* The .step param run command was added to the netlist. Starts at -1 which it's the nominal value simulation, and
 finishes that the number of simulations specified in the prepare_testbench() method.
* A default value for the run parameter was added. This is useful if the .step param run is commented out.
* The R1 tolerance is different from the other resistors. This is because the tolerance was explicitly set for R1.
* The Vos parameter was added to the .param list. This is because the parameter was explicitly set using the
set_parameter_deviation method.
* Functions utol, ntol and urng were added to the .func list. These functions are used to generate random values.
Uniform distributions use the LTSpice built-in mc(x, tol) and flat(x) functions, while normal distributions use the gauss(x) function.

Similarly, the worst case analysis can also be setup by using the class WorstCaseAnalysis, as exemplified below:

```python
import logging

import spicelib
from spicelib import AscEditor, SimRunner  # Imports the class that manipulates the asc file
from spicelib.sim.tookit.worst_case import WorstCaseAnalysis
from spicelib.simulators.ltspice_simulator import LTspice

spicelib.set_log_level(logging.INFO)

sallenkey = AscEditor("./testfiles/sallenkey.asc")  # Reads the asc file into memory
runner = SimRunner(simulator=LTspice, output_folder='./temp_wca', verbose=True)  # Instantiates the runner with a temp folder set
wca = WorstCaseAnalysis(sallenkey, runner)  # Instantiates the Worst Case Analysis class

# The following lines set the default tolerances for the components
wca.set_tolerance('R', 0.01)  # 1% tolerance
wca.set_tolerance('C', 0.1)  # 10% tolerance
# wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant
wca.set_tolerance('I', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant
# Some components can have a different tolerance
wca.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1
wca.set_tolerance('R4', 0.0)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well.
wca.set_parameter_deviation('Vos', 3e-4, 5e-3)

# Finally the netlist is saved to a file
wca.save_netlist('./testfiles/sallenkey_wc.asc')
```

-- in examples/run_worst_case.py [Example 1]

When opening the created sallenkey_wc.net file, we can see that the following circuit.

![Sallen-Key Amplifier with WCA](./doc/modules/sallenkey_wc.png "Sallen-Key Amplifier with WCA")

The following updates were made to the circuit:

* The value of each component was replaced by a function that generates a nominal, minimum and maximum value depending
on the run parameter and is assigned a unique index number. (R1=0, Vos=1, R2=2, ... V2=7, VIN=8)
The unique number corresponds to the bit position of the run parameter. Bit 0 corresponds to the minimum value and
bit 1 corresponds to the maximum value. Calculating all possible permutations of maximum and minimum values for each
component, we get 2**9 = 512 possible combinations. This maps into a 9 bit binary number, which is the run parameter.
* The .step param run command was added to the netlist. It starts at -1 which it's the nominal value simulation, then 0
which corresponds to the minimum value for each component, then it makes all combinations of minimum and maximum values until 511, which is the simulation with all maximum values.
* A default value for the run parameter was added. This is useful if the .step param run is commented out.
* The R1 tolerance is different from the other resistors. This is because the tolerance was explicitly set for R1.
* The wc() function is added to the circuit. This function is used to calculate the worst case value for each component,
given a tolerance value and its respective index.
* The wc1() function is added to the circuit. This function is used to calculate the worst case value for each component,
given a minimum and maximum value and its respective index.

### ltsteps.py ###

This module defines a class that can be used to parse LTSpice log files where the information about .STEP information is
written. There are two possible usages of this module, either programmatically by importing the module and then
accessing data through the class as exemplified here:

```python
#!/usr/bin/env python
# coding=utf-8

from spicelib.log.ltsteps import LTSpiceLogReader

data = LTSpiceLogReader("./testfiles/Batch_Test_AD820_15.log")

print("Number of steps  :", data.step_count)
step_names = data.get_step_vars()
meas_names = data.get_measure_names()

# Printing Headers
print(' '.join([f"{step:15s}" for step in step_names]), end='')  # Print steps names with no new line
print(' '.join([f"{name:15s}" for name in meas_names]), end='\n')
# Printing data
for i in range(data.step_count):
    print(' '.join([f"{data[step][i]:15}" for step in step_names]), end='')  # Print steps names with no new line
    print(' '.join([f"{data[name][i]:15}" for name in meas_names]), end='\n')  # Print Header

print("Total number of measures found :", data.measure_count)
```

-- in examples/ltsteps_example.py

The second possibility is to use the module directly on the command line

## Command Line Interface ##

The following tools will be installed when you install the library via pip. The extension '.exe' is only available on Windows, on MacOS or Linux, the commands will have the same name, but without '.exe'. The executables are simple links to python scripts with the same name, of which the majority can be found in the package's 'scripts' directory.

### ltsteps.py ###

```bash
Usage: ltsteps [filename]
```

The `filename` can be either be a log file (.log), a data export file (.txt) or a measurement output file (.meas)
This will process all the data and export it automatically into a text file with the extension (tlog, tsv, tmeas)
where the data read is formatted into a more convenient tab separated format. In case the `filename` is not provided, the
script will scan the directory and process the newest log, txt or out file found.

### histogram.py ###

This module uses the data inside on the filename to produce a histogram image.

 ```bash
Usage: histogram [options] LOG_FILE TRACE

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -s SIGMA, --sigma=SIGMA
                        Sigma to be used in the distribution fit. Default=3
  -n NBINS, --nbins=NBINS
                        Number of bins to be used in the histogram. Default=20
  -c FILTERS, --condition=FILTERS
                        Filter condition writen in python. More than one
                        expression can be added but each expression should be
                        preceded by -c. EXAMPLE: -c V(N001)>4 -c parameter==1
                        -c  I(V1)<0.5
  -f FORMAT, --format=FORMAT
                        Format string for the X axis. Example: -f %3.4f
  -t TITLE, --title=TITLE
                        Title to appear on the top of the histogram.
  -r RANGE, --range=RANGE
                        Range of the X axis to use for the histogram in the
                        form min:max. Example: -r -1:1
  -C, --clipboard       If the data from the clipboard is to be used.
  -i IMAGEFILE, --image=IMAGEFILE
                        Name of the image File. extension 'png'    
 ```

### raw_convert.py ###

A tool to convert .raw files into csv or Excel files.

```bash
Usage: raw_convert [options] <rawfile> <trace_list>

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -o FILE, --output=FILE
                        Output file name. Use .csv for CSV output, .xlsx for
                        Excel output
  -c, --clipboard       Output to clipboard
  -v, --verbose         Verbose output
  -s SEPARATOR, --sep=SEPARATOR
                        Value separator for CSV output. Default: "\t" <TAB>
                        Example: -d ";"
```

### rawplot.py ###

Uses matplotlib to plot the data in the raw file.

```bash
Usage: rawplot RAW_FILE TRACE_NAME
```

### run_server.py ###

This module is used to run a server that can be used to run simulations in a remote machine. The server will run in the
background and will wait for a client to connect. The client will send a netlist to the server and the server will run
the simulation and return the results to the client. The client on the remote machine is a script instancing the
SimClient class. An example of its usage is shown below:

```python
import os
import zipfile
import logging

# In order for this, to work, you need to have a server running. To start a server, run the following command:
# python -m spicelib.run_server --port 9000 --parallel 4 --output ./temp

_logger = logging.getLogger("spicelib.SimClient")
_logger.setLevel(logging.DEBUG)

from spicelib.client_server.sim_client import SimClient

server = SimClient('http://localhost', 9000)
print(server.session_id)
runid = server.run("./testfiles/testfile.net")
print("Got Job id", runid)
for runid in server:  # Ma
    zip_filename = server.get_runno_data(runid)
    print(f"Received {zip_filename} from runid {runid}")
    with zipfile.ZipFile(zip_filename, 'r') as zipf:  # Extract the contents of the zip file
        print(zipf.namelist())  # Debug printing the contents of the zip file
        zipf.extract(zipf.namelist()[0])  # Normally the raw file comes first
    os.remove(zip_filename)  # Remove the zip file

server.close_session()
```

-- in examples/sim_client_example.py [SimClient Example]

```bash
usage: run_server [-h] [-p PORT] [-o OUTPUT] [-l PARALLEL] simulator

Run the LTSpice Server. This is a command line interface to the SimServer class. The SimServer class is used to run
simulations in parallel using a server-client architecture. The server is a machine that runs the SimServer class and
the client is a machine that runs the SimClient class. The argument is the simulator to be used (LTSpice, Ngspice, XYCE, etc.)

positional arguments:
  simulator             Simulator to be used (LTSpice, Ngspice, XYCE, etc.)

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  Port to run the server. Default is 9000
  -o OUTPUT, --output OUTPUT
                        Output folder for the results. Default is the current folder
  -l PARALLEL, --parallel PARALLEL
                        Maximum number of parallel simulations. Default is 4
```

### asc_to_qsch.py ###

Converts LTspice schematics into QSPICE schematics.

```bash
Usage: asc_to_qsch [options] ASC_FILE [QSCH_FILE]

Options:
  --version            show program's version number and exit
  -h, --help           show this help message and exit
  -a PATH, --add=PATH  Add a path for searching for symbols
```

### log\semi_dev_op_reader.py ###

This module is used to read from LTSpice log files Semiconductor Devices Operating Point Information. A more detailed
documentation is directly included in the source file docstrings.

## Debug Logging ##

The library uses the standard `logging` module. Three convenience functions have been added for easily changing logging
settings across the entire library. `spicelib.all_loggers()` returns a list of all the logger's
names, `spicelib.set_log_level(logging.DEBUG)`
would set the library's logging level to debug, and `spicelib.add_log_handler(my_handler)` would add `my_handler` as a
handler for all loggers.

### Single Module Logging ###

It is also possible to set the logging settings for a single module by using its name acquired from
the `spicelib.all_loggers()`
function. For example:

```python
import logging

logging.basicConfig(level=logging.INFO)  # Set up the root logger first

import spicelib  # Import spicelib to set the logging levels

spicelib.set_log_level(logging.DEBUG)  # Set spicelib's global log level
logging.getLogger("spicelib.RawRead").level = logging.WARNING  # Set the log level for only RawRead to warning
```

Would set only `spicelib.RawRead` file's logging level to warning while the other modules would remain at debug level.
_Make sure to initialize the root logger before importing the library to be able to see the logs._

## To whom do I talk to? ##

* Tools website : [https://www.nunobrum.com/pyltspice.html](https://www.nunobrum.com/pyltspice.html)
* Repo owner : [me@nunobrum.com](me@nunobrum.com)
* Alternative contact : <nuno.brum@gmail.com>

## History ##
* Version 1.2.0
  * Implementing a new approach to the accessing component values and parameters. Instead of using the 
  get_component_value() and get_component_parameters() methods, the component values and parameters are now accessed 
  directly as attributes of the component object. This change was made to make the code more readable.
  The old methods are still available for backward compatibility. 
  * Improvements on the documentation.
  * Added testbench for the regular expressions used on the SpiceEditor. Improvements on the regular expressions.
  * Improvements on the usage of spicelib in Linux using wine.
* Version 1.2.0
  * Fix on line patterns on the AsyEditor (#PR 65)
  * Fix on the X (.SUBCKT) components regex (#PR 66)
* Version 1.1.3
  * Implementing a set_component_parameters() and get_component_parameters() method on the Editor classes.
    This method allows to set and get the parameters of a component.
  * Bug Fixes:
    * AscEditor was hanging in comments. Issue #43
    * Supporting other text orientations on the AscEditor. Issue #44
    * Allow other encodings in AscEditor. Issues #45 and #48
  * Supporting lines, rectangles, circles and arcs in AscEditor.
  * Improving the regex for the component values in the SpiceEditor.
* Version 1.1.2
  * Fixes on the readme_update.py script. Was not supporting spaces after the []
  * Solving issue PyLTspice Issue #138. Hierarchical edits to ASC files are now supported.
* Version 1.1.1
  * Supporting hierarchical edits on both QSPICE and LTspice schematics
  * Skipping the need of the rich library on examples
  * Giving feedback on the search for symbols on the ASC to QSCH conversion
  * Improvement on Documentation
  * Adding examples and unittests on hiearchical edits
  * Giving access to hidden properties (asc_file_path in AscEditor and qsch_file_path in QschEditor)
  * Refactoring save_netlist() method in QschEditor class
  * Supporting arcs and rectangles on AsyReader
  * Adding file_search.py containing utility functions for searching files
  * Adding windows_short_names.py containing a code to get the 8.3 Windows short names.
* Version 1.1.0
  * First usable version of a LTspice to QSPICE schematic converter.
* Version 1.0.4
  * Adding the missing the asc_to_qsch_data.xml to the package
  * Adding a MANIFEST.in to the project
  * Adding keywords to the project.toml
* Version 1.0.3
  * Correcting the generation of a .net from the QschEditor.
* Version 1.0.2
  * Correction on the log file data export. Each column is guaranteed to have its own title.
  * Fixes on the generation of netlists from QSPICE Schematic files
* Version 1.0.1
  * Timeout always default to No timeout.
  * Restructure the way netlists are read and written, so to be able to read and write netlists from different simulator
    schematics.
  * Added a method add_sources() to copy files from the client to the spice server.  
  * Moving CLI scripts to their own directory
  * Adding a script that allows to insert code into a README.md file
  * Supporting capital "K" for kilo in the spice and schematic editors.
* Vesion 0.9
  * SimAnalysis supporting both QSPICE and LTSpice logfiles.
  * FastWorstCaseAnalysis algorithm implemented
  * Fix on the log reading of fourier data.
  * Adding a parameter host to the SimServer class which then passed to the SimpleXMLRPCServer.
* Version 0.8
  * Important Bugfix on the LTComplex class.
  * Fixes and enhancing the analysis toolkit.
* Version 0.7
  * Setting the default verbose to False.
  * Implementing the Sensitivity Analysis.
  * Improving the sim_analysis so to be able to analyse simulation results.
  * Renamed editors .write_netlist() to .save_netlist(). The former is kept
    for legacy purposes.
  * Improving the get_measure_value() method to be able to return the value
    of a measure in a specific step.
* Version 0.6
  * Implementing a conversion from QSPICE Schematics .qsch to spice files
  * Improving the Analysis Toolkit to support adding instructions directly
  to the WorstCase and Montecarlo classes.
  * Using dataclasses to store the fourier information on LTSpiceLogReader.
  * Exporting fourier data into a separate log file: `logfile`.fourier
  * Making LTComplex a subclass of Python built-in complex class.
* Version 0.5
  * Reading QSPICE .AC and .OP simulation results from qraw files
  * Parsing of QSPICE log and measure files
  * Enabling the Histogram.py to read log files directly (only for LTSpice)
  * Fixing a bug on the LTSpiceLogReader class that was not correctly exporting
  the data when there fourier data was present.
  * Enabling the creation of blank netlists (Thanks to @rliangcn)
  * Correction on the Mac OSX process name for LTSpice (Thanks to Wynand M.)
* Version 0.4
  * Implementing the callback argument in the SimRunner class.
  * Moved simulator classes into a separate package.
* Version 0.3
  * Cloning and renaming from PyLTSpice 4.1.2
  * Starting at 0.3 to align with the spicelib in PyPi
