# README <!-- omit in toc -->

_current version: 1.4.2_

*spicelib* is a toolchain of python utilities design to interact with spice simulators, as for example:

* LTspice
* Ngspice
* QSPICE
* Xyce

**Table of Contents**

- [What is contained in this repository](#what-is-contained-in-this-repository)
    - [Main Tools](#main-tools)
    - [Main Classes](#main-classes)
- [How to Install](#how-to-install)
    - [Updating spicelib](#updating-spicelib)
    - [Using GITHub](#using-github)
- [How to use](#how-to-use)
- [LICENSE](#license)
- [Main modules](#main-modules)
    - [RawRead](#rawread)
    - [RawWrite](#rawwrite)
    - [SpiceEditor, AscEditor, QschEditor and SimRunner](#spiceeditor-asceditor-qscheditor-and-simrunner)
        - [Simulators and Windows, Linux and MacOS compatibility](#simulators-and-windows-linux-and-macos-compatibility)
        - [Executable and Library paths](#executable-and-library-paths)
        - [Runner log redirection](#runner-log-redirection)
        - [Adding search paths for symbols and library files](#adding-search-paths-for-symbols-and-library-files)
        - [Limitations and specifics of AscEditor](#limitations-and-specifics-of-asceditor)
        - [Hierarchial circuits: reading and editing](#hierarchial-circuits-reading-and-editing)
    - [Simulation Analysis Toolkit](#simulation-analysis-toolkit)
    - [ltsteps](#ltsteps)
- [Command Line Interface](#command-line-interface)
    - [ltsteps.exe](#ltstepsexe)
    - [histogram.exe](#histogramexe)
    - [raw\_convert.exe](#raw_convertexe)
    - [rawplot.exe](#rawplotexe)
    - [run\_server.exe](#run_serverexe)
    - [asc\_to\_qsch.exe](#asc_to_qschexe)
- [Other functions](#other-functions)
    - [log\\semi\_dev\_op\_reader.opLogReader](#logsemi_dev_op_readeroplogreader)
- [Debug Logging](#debug-logging)
    - [Single Module Logging](#single-module-logging)
- [To whom do I talk?](#to-whom-do-i-talk)
- [History](#history)

## What is contained in this repository

### Main Tools

* __Analysis Toolkit__
  A set of tools that prepare an LTspice netlist for a Montecarlo or Worst Case Analysis. The device tolerances are set
  by the user and the netlist is updated accordingly. The netlist can then be used with the SimRunner to run a batch of
  simulations or with the LTspice GUI.

* __ltsteps.exe__
  An utility that extracts from LTspice output files data, and formats it for import in a spreadsheet, such like Excel
  or Calc.

* __histogram.exe__
  A python script that uses numpy and matplotlib to create a histogram and calculate the sigma deviations. This is
  useful for Monte-Carlo analysis.

(Note that the extension '.exe' is only available on Windows. On MacOS or Linux, the commands will have the same name,
but without '.exe')

### Main Classes

* __AscEditor/QschEditor/SpiceEditor__
  Classes for the manipulation of respectively:

    * LTspice `.asc` files
    * QSPICE `.qsch` files
    * SPICE netlists (from no matter what simulator)

  without having to open the schematic in a GUI. The simulations can then be run in batch mode (see SimRunner). Examples
  of functions provided:

```python
from spicelib.editor import SpiceEditor

netlist = SpiceEditor("example.net")
netlist.set_element_model('D1', '1N4148')  # Replaces the Diode D1 with the model 1N4148
netlist.set_component_value('R2', '33k')  # Replaces the value of R2 by 33k
netlist['R2'].value = 33000  # Same as above
netlist.set_component_value('V1', '5')  # Replaces the value of V1 by 5
netlist['V1'].value = 5  # Same as above
netlist.set_parameters(run=1, TEMP=80)  # Creates or updates the netlist to have .PARAM run=1 or .PARAM TEMP=80
netlist.add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")
netlist.remove_instruction(".STEP run -1 1023 1")  # Removes previously added instruction
netlist.reset_netlist()  # Resets all edits done to the netlist.
netlist.set_component_parameters('R1', temp=25, pwr=None)  # Sets or removes additional parameters
netlist['R1'].set_params(temp=25, pwr=None)  # Same as above
# The two equivalent instructions below manipulate X1 instance of a subcircuit.
netlist.get_subcircuit('X1').set_component_parameters('R1', temp=25, pwr=None)  # Sets or removes on a component
netlist['X1:R1'].params = dict(temp=25, pwr=None)  # Same as above
# the  instructions below update a subcircuit, which will impact all its instances
subc = netlist.get_subcircuit_named("MYSUBCKT")
subc.set_component_parameters('R1', 'R1', temp=25, pwr=None)  # sets temp to 25 and removes pwr
subc['R1'].params = dict(temp=25, pwr=None)  # same as the above instruction
# The next two equivalent instructions set the R1 value on .SUBCKT MYSUBCKT R1 to 1k 
subc.set_component_value('R1', 1000)
subc['R1'].value = 1000  # Same as the above
```

* __SimRunner__
  A class that can be used to run LTspice/QSPICE/Ngspice/Xyce simulations in batch mode without having to open the
  corresponding GUI.
  This, in cooperation with the above mentioned xxxEditor classes, is useful because:

    * It can overcome the limitation of only stepping 3 parameters
    * Different types of simulations .TRAN .AC .NOISE can be run in a single batch
    * The RAW Files are smaller and easier to handle
    * When used with RawRead and ltsteps, validation of the circuit can be done automatically
    * Different models can be simulated in a single batch

* __RawRead__
  A class that serves to read raw files into a python class.

* __RawWrite__
  A class to write RAW files that can be read by the LTspice Wave Application.

## How to Install

`pip install spicelib`

### Updating spicelib

`pip install --upgrade spicelib`

### Using GITHub

`git clone https://github.com/nunobrum/spicelib.git`

If using this method it would be good to add the path where you cloned the site to python path.

`import sys`  
`sys.path.append(<path to spicelib>)`

## How to use

Here follows a quick outlook on how to use each of the tools.

More comprehensive documentation can be found in <https://spicelib.readthedocs.io/en/latest/>

## LICENSE

GNU V3 License
(refer to the LICENSE file)

## Main modules

### RawRead

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

### RawWrite

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

### SpiceEditor, AscEditor, QschEditor and SimRunner

These modules are used to prepare and launch SPICE simulations.

The editors can be used change component values, parameters or simulation commands. After the simulation is run, the
results then can be processed with either the RawRead or with the LTSpiceLogReader module to read the log file which can
contain .MEAS results.

Here follows an example of operation.

```python
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
```

-- in examples/sim_runner_example.py

The example above is using the SpiceEditor to modify a spice netlist, but it is also possible to use the AscEditor to
directly modify a .asc file. The edited .asc file can be opened by the LTspice GUI and the simulation can be run from
there. It is also possible to open a .asc file and to generate a spice netlist from it.

#### SimStepper

To avoid having loops inside loops spicelib can handle the work of making multi-dimensional sweeps using the SimStepper
class. The code in the previous section can be writen as shown here.

```python
import os

from spicelib import SpiceEditor, SimRunner
from spicelib.simulators.ltspice_simulator import LTspice
from spicelib.sim.sim_stepping import SimStepper


def processing_data(raw_file, log_file):
    print("Handling the simulation data of %s" % log_file)


runner = SimRunner(parallel_sims=4, output_folder='./temp2', simulator=LTspice)

# select spice model
Stepper = SimStepper(SpiceEditor("./testfiles/Batch_Test.net"), runner)
# set default arguments

Stepper.set_parameters(res=0, cap=100e-6)
Stepper.set_component_value('R2', '2k')
Stepper.set_component_value('R1', '4k')
Stepper.set_element_model('V3', "SINE(0 1 3k 0 0 0)")
# define simulation
Stepper.add_instructions(
    "; Simulation settings",
    ";.param run = 0"
)
Stepper.set_parameter('run', 0)
Stepper.set_parameter('test_param2', 20)
Stepper.add_model_sweep('XU1', ('AD712', 'AD820_ALT'))
Stepper.add_value_sweep('V1', (5, 10, 15))
# Stepper.add_value_sweep('V1', (-5, -10, -15))

run_netlist_file = "run_OPAMP_{XU1}_VDD_{V1}.net"
Stepper.run_all(callback=processing_data, filenamer=run_netlist_file.format)

# Sim Statistics
print('Successful/Total Simulations: ' + str(Stepper.okSim) + '/' + str(Stepper.runno))
Stepper.export_step_info("./temp2/export.csv")
runner.cleanup_files()
```

-- in examples/sim_stepper_example.py

The SimStepper methods

 * add_value_sweep(ref, iterable) 
 * add_model_sweep(ref, iterable) 
 * add_param_sweep(name, iterable) 

receive as first argument the component or parameter reference as the first argument and an iterable object such as a 
list or a generator as a second argument. 

When the run_all() method is called, it will make run a simulation per each combination of values. On the example above 
it will make the simulations: 

`(XU1, V1) in (("AD712", 5), ("AD712", 10), ("AD712", 15), ("AD820_ALT", 5), ("AD820_ALT", 10), ("AD820_ALT", 15))`   

It should be noted that for each sweep method added it will add a new dimension simulation space. 
In other words, the total number of simulations will be the product of each vector length. There is no restriction to
the number of simulations to be done, however, a huge number of simulation will take a long time to execute and may
occupy a considerable amount of space on the disk.

#### Simulators and Windows, Linux and MacOS compatibility

The **LTspice** class tries to detect the correct path of the LTspice installation depending on the platform. On Linux
it expects LTspice to be installed under wine. On MacOS, it first looks for LTspice installed under wine, and when it
cannot be found, it will look for native LTspice. The reason is that the command line interface of the native LTspice is
severely limited.

If you use the native LTspice, please make sure that you have installed the libraries via Settings: `Operation`
tab, `Model Update` button.

**Ngspice** runs natively under Windows, Linux and MacOS (via brew). This library works with Ngspice CLI, and tries to
detect the correct executable path, no matter the platform. It cannot (yet) work with the shared library version of
Ngspice that is delivered with for example Kicad, you will need to install the CLI version. You can however use Kicad as
the schema editor and subsequently save the Ngspice netlist to use it with this library.

For the other simulators, built-in Linux/MacOS support is coming, but you can always try to use it under Linux via
setting of the executable paths.

#### Executable and Library paths

A large variety of standard paths are automatically detected. To see what paths are detected:

```python
from spicelib.sim.sim_runner import SimRunner
from spicelib.simulators.ltspice_simulator import LTspice

runner = SimRunner(output_folder='./tmp', simulator=LTspice)
# Show the executable path
print(runner.simulator.spice_exe)
print(runner.simulator.process_name)
# Show the default library paths of that simulator. This is deduced from `spice_exe`
print(runner.simulator.get_default_library_paths())
```

If you want, you can set your own **executable paths**, via the two variables shown above:

* `spice_exe`: a list of with the commands that invoke the sumulator. Do not include command line options to the
  simulator here.
* `process_name`: the process name as visible to the OS.

You can also use `simulator.create_from()`.

The **library paths** are needed for the editors. However, the default library paths depend on the simulator used, its
installation path, and if that simulator runs under wine or not. The function `editor.prepare_for_simulator()` allows
you to tell the editor what simulator is used, and its library paths. This not always needed however:

* `AscEditor` and `SpiceEditor` presume that LTspice is used.
* `QschEditor` presumes that QSPICE is used.

This will of course not work out if you use the editors on other simulators (as can be the case with `SpiceEditor`), or
if you have manually set the simulator's executable path. In those cases you will want to inform your editor of that
change via `editor.prepare_for_simulator()`.

If you want, you can also specify library and symbol search paths using `editor.set_custom_library_paths()`.

**Example**:

```python
# ** Simulator executable paths
from spicelib.simulators.ltspice_simulator import LTspice
from spicelib.sim.sim_runner import SimRunner
from spicelib.editor.asc_editor import AscEditor


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
AscEditor.set_custom_library_paths("/mypath/lib/sub",
                                   "/mypath/lib/sym",
                                   "/mypath/lib/sym/OpAmps",
                                   "/mypath/lib/cmp")

```

#### Runner log redirection

When you use wine (on Linux or MacOS) or a simulator like NGspice, or if you run simultaneous simulators,
you may want to redirect the output of `run()` or `run_now()` or `create_netlist()`, as it prints a lot of
console messages without much value. Real time redirecting to the logger is unfortunately not easy, especially
with the simultaneous runner. You can redirect the output for example with:

```python
# force command console output to a separate file, which is
# named like the netlist file, but with extension ".exe.log"
runner.run(netlist, exe_log=True)
```

This is supported on both the SimRunner and directly on the various simulators (LTspice,..).
The runner client server function (see `SimClient`) does not (yet) support this, but it is less bothersome there.

#### Adding search paths for symbols and library files

LTspice allows users to add Search Paths for symbol and libraries. This is very helpful when sharing non-native
libraries and symbols between different projects. The `spicelib` supports this feature by using the
set_custom_library_paths() class method as is exemplified in the code snippet below.

```python
from spicelib import AscEditor

AscEditor.set_custom_library_paths([r"C:\work\MyLTspiceSymbols", r"C:\work\MyLTspiceLibraries"])
```

The user can specify one or more search paths. Note that each call to this method will invalidate previously set search
paths. Also, note that this is a class method in all available editors, [SpiceEditor, AscEditor and QschEditor], this
means that updating one instantiation, will update all other instances of the same class.

#### Limitations and specifics of AscEditor

AscEditor has some limitations and differences in regard to SpiceEditor.

* As is visible in the LTspice GUI, it groups all component properties/parameters in different 'attributes' like '
  Value', 'Value2', 'SpiceLine', 'SpiceLine2'. Netlists do not have that concept, and place everything in one big list,
  that SpiceEditor subsequently separates in 'value' and 'parameters' for most components. To complicate things, LTspice
  distributes the parameters over all 4 attributes, with varying syntax. You must be aware of how LTspice handles the
  parameter placement if you use AscEditor.

  `AscEditor.get_component_parameters()` will show the native attributes, and tries to disect 'SpiceLine' and '
  SpiceLine2', just like `SpiceEditor.get_component_parameters()` would do.
  This means for example for a Voltage source of DC 2V, with small signal analysis AC amplitude of 1V and a series
  resistance of 3 ohm:
    * `AscEditor.get_component_value()` and `SpiceEditor.get_component_value()` -> `'2 AC 1'`
    * `AscEditor.get_component_parameters()` -> `{'Value': '2', 'Value2': 'AC 1', 'SpiceLine': 'Rser=3', 'Rser': 3}`
    * `SpiceEditor.get_component_parameters()` -> `{'Rser': 3}`
    * Please note that if you want to remove the small signal analysis AC amplitude, you MUST use
        * `AscEditor.set_component_parameters(..,'Value2','')`, as `set_component_value()` will only affect 'Value'
        * `SpiceEditor.set_component_value(..,'2')`
    * with both editors, you can use `...set_component_parameters(.., Rser=5)`
* When adressing components, SpiceEditor requires you to include the prefix in the component name, like `XU1` for an
  OpAmp. AscEditor will require `U1`.
* AscEditor and SpiceEditor only work with the information in their respective schema/circuit files. The problem is that
  LTspice does not store any of the underlying symbol's default parameter values in the .asc files. SpiceEditor works on
  netlists, and netlists do contain all parameters.

  This can affect the behaviour when using symbols like `OpAmps/UniversalOpAmp2`. Although the LTspice GUI shows the
  parameters like `Avol`, `GBW` and `Vos`, even when they have the default
  values, `AscEditor.get_component_parameters()` will not return these parameters unless they have been
  modified. `SpiceEditor.get_component_parameters()` on the contrary will show all parameters, regardless of if they
  were modified. It is however possible for AscEditor to set or modify the parameters
  with `AscEditor.set_component_parameters()`.
  Example:  `set_component_parameters("U1", Value2="Avol=2Meg GBW=10Meg Slew=10Meg")`.

  Note here that you must know the correct attribute holding that parameter, and make sure that you know and set all the
  other parameters in that attribute. If the attribute is in 'SpiceLine' however (as with the majority of the simpler
  components), you may address the parameter individually (see the voltage source example above).

Resumed, it is better to use SpiceEditor than AscEditor, as it is more straightforward. On MacOS, it is recommended to
use LTspice under wine, or to export the netlist manually, as MacOS's LTspice does not support automated export of
netlists.

#### Hierarchial circuits: reading and editing

* Circuits can refer to other circuits (subcircuits) and to components, be it from other circuit or netlist files, or
  from libraries.
* Subcircuits can contain other subcircuits
* Internal components in components/subcircuits that are loaded from libraries can be read, but not modified.

Examples:

Imagine a top circuit that refers to a subcircuit 'X1' that is not in a library,
but in a separate '.asc' or '.net' file (depending on your editor).
That subcircuit has a compoment 'L1'.

The following is all possible:

```python
import spicelib

# my_edt = spicelib.AscEditor("top_circuit.asc")
my_edt = spicelib.SpiceEditor("top_circuit.net")  # or from a netlist...

print(my_edt.get_subcircuit("X1").get_components())  # prints ['C1', 'X2', 'L1']

# The following are equivalent:
v = my_edt.get_component_value("X1:L1")
v = my_edt.get_subcircuit("X1").get_component_value("L1")
v = my_edt["X1:L1"].value

# Likewise, the following are equivalent:
# Note that this will not work if the component X1 is from a library. See note 3 below.
my_edt.set_component_value("X1:L1", 2e-6)  # sets L1  in X1 instance to 2uH
my_edt["X1:L1"].value = 2e-6  # Same as the instruction above

# Likewise, for accessing parameters the following are equivalent:
l = my_edt.get_subcircuit("X1").get_component_parameters('C1')
l = my_edt["X1:C1"].params

# Likewise, the following are equivalent:
# Note that this will not work if the component X1 is from a library. See note 3 below.
my_edt.get_subcircuit("X1").set_component_parameters("C1", Rser=1)
my_edt["X1:C1"].set_params(Rser=1)
my_edt["X1:C1"].params = dict(Rser=1)

# The same goes for SpiceEditor, only that you should use 'XX1' instead of 'X1'
```

*NOTE 1: The code above sets only the instance of a subcircuit. A copy of it is done prior to making edits.
To update all instances of a subcircuit, the subcircuit needs to be be manipulated directly, as is done below.*

*NOTE 2: This implementation changes on the AscEditor and QschEditor.*

*NOTE 3: You cannot modify values or parameters of components/subcircuits from a library. An exception will
occur in that case. If you want to modify, you should therefore include the component/subcircuit in your file.
It may be best to rename that subcircuit, since ltspice 24+ will not allow a 'local' subcircuit and a lib to
refer to the same subcircuit name. You can only avoid renaming it if you no longer use the subcircuit under
its original name.
Know that executing any of the 'write' commands creates a new subcircuit under a new name, called
`{subcircuit_model_name}_{component_name}`, like `AD820_X1`, and sets the model of `X1` to `AD820_X1`.*

```python
import spicelib

my_edt = spicelib.SpiceEditor("top_circuit.net")
my_sub = my_edt.get_subcircuit_named("MYSUBCKT")

print(my_sub.get_components())  # prints ['C1', 'X2', 'L1']

# The following are equivalent:
v = my_sub.get_component_value("L1")
v = my_sub["L1"].value

# Note that this will not work if the component X1 is from a library. An exception will occur in that case.
my_sub.set_component_value("L1", 2e-6)  # sets L1  in X1 instance to 2uH
my_sub["L1"].value = 2e-6  # Same as the instructionn above

# Likewise, for accessing parameters the following are equivalent:
l = my_sub.get_component_parameters('C1')
l = my_sub["C1"].params

# Likewise, the following are equivalent:
# Note that this will not work if the component X1 is from a library. An exception will occur in that case.
my_sub.set_component_parameters("C1", Rser=1)
my_sub["C1"].set_params(Rser=1)
my_sub["C1"].params = dict(Rser=1)
```

### Simulation Analysis Toolkit

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

manually_simulating_in_LTspice = False

if manually_simulating_in_LTspice:
    # Finally the netlist is saved to a file. This file contains all the instructions to run the simulation in LTspice
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
  Uniform distributions use the LTSpice built-in mc(x, tol) and flat(x) functions, while normal distributions use the
  gauss(x) function.

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
  which corresponds to the minimum value for each component, then it makes all combinations of minimum and maximum
  values until 511, which is the simulation with all maximum values.
* A default value for the run parameter was added. This is useful if the .step param run is commented out.
* The R1 tolerance is different from the other resistors. This is because the tolerance was explicitly set for R1.
* The wc() function is added to the circuit. This function is used to calculate the worst case value for each component,
  given a tolerance value and its respective index.
* The wc1() function is added to the circuit. This function is used to calculate the worst case value for each
  component,
  given a minimum and maximum value and its respective index.

### ltsteps

This module defines a class that can be used to parse LTSpice log files where the information about .STEP information is
written. There are two possible usages of this module, either programmatically by importing the module and then
accessing data through the class as exemplified here:

```python
#!/usr/bin/env python
# coding=utf-8

from spicelib.log.ltsteps import LTSpiceLogReader

data = LTSpiceLogReader("./testfiles/Batch_Test_Simple_1.log")

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

## Command Line Interface

The following tools will be installed when you install the library via pip. The extension '.exe' is only available on
Windows. On MacOS or Linux, the commands will have the same name, but without '.exe'. The executables are simple links
to python scripts with the same name, of which the majority can be found in the package's 'scripts' directory.

### ltsteps.exe

```text
Usage: ltsteps [filename]
```

The `filename` can be either be a log file (.log), a data export file (.txt) or a measurement output file (.meas)
This will process all the data and export it automatically into a text file with the extension (tlog, tsv, tmeas)
where the data read is formatted into a more convenient tab separated format. In case the `filename` is not provided,
the
script will scan the directory and process the newest log, txt or out file found.

### histogram.exe

This module uses the data inside on the filename to produce a histogram image.

 ```text
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

### raw_convert.exe

A tool to convert .raw files into csv or Excel files.

```text
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

### rawplot.exe

Uses matplotlib to plot the data in the raw file.

```text
Usage: rawplot RAW_FILE TRACE_NAME
```

### run_server.exe

This module is used to run a server that can be used to run simulations in a remote machine. The server will run in the
background and will wait for a client to connect. The client will send a netlist to the server and the server will run
the simulation and return the results to the client. The client on the remote machine is a script instancing the
SimClient class. An example of its usage is shown below:

```python
import os
import zipfile
import logging

# In order for this, to work, you need to have a server running. To start a server, run the following command:
# python -m spicelib.scripts.run_server --port 9000 --parallel 4 --output ./temp LTSpice 300

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

```text
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

### asc_to_qsch.exe

Converts LTspice schematics into QSPICE schematics.

```text
Usage: asc_to_qsch [options] ASC_FILE [QSCH_FILE]

Options:
  --version            show program's version number and exit
  -h, --help           show this help message and exit
  -a PATH, --add=PATH  Add a path for searching for symbols
```

## Other functions

### log\semi_dev_op_reader.opLogReader

This module is used to read from LTSpice log files Semiconductor Devices Operating Point Information. A more detailed
documentation is directly included in the Python Modules documentation under "Semiconductor Operating Point Reader".

## Debug Logging

The library uses the standard `logging` module. Three convenience functions have been added for easily changing logging
settings across the entire library. `spicelib.all_loggers()` returns a list of all the logger's
names, `spicelib.set_log_level(logging.DEBUG)`
would set the library's logging level to debug, and `spicelib.add_log_handler(my_handler)` would add `my_handler` as a
handler for all loggers.

### Single Module Logging

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

## To whom do I talk?

For support and improvement requests please open an Issue
in [GitHub spicelib issues](https://github.com/nunobrum/spicelib/issues)

## History

* Version 1.4.2
    * SimRunner runno, okSim and failSim are now readonly attributes
    * SimStepper now stores all netlist updates. This information can now be exported to a CSV file.
    * Fixed Issue #169 - Issue with Embedded .model Symbol Properties When Using Pipe Prefix
    * Fixed Issue #170 - set_parameter does not update parameter in simulation netlist generated by QschEditor
* Version 1.4.1
    * Fixed Issue #158 - improve xyce path detection, improve runner switch parameter help texts
    * Fixed Issue #154 - support embedded subcircuits in Qspice
    * Fixed Issue #139 - support xyce raw files
    * Added `get_all_parameter_names()` function to all editors (#159)
* Version 1.4.0 (Python 3.9+ only)
    * Fixed Issue #152 - python version compatibility too limited on PyPi.
* Version 1.3.8
    * Solving deprecation in GitHub artifact actions v3 -> v4
* Version 1.3.7
    * Fixed Issue #143 - ltsteps example fixed
    * Fixed Issue #141 - Raw file reader cannot handle complex values (AC analysis) in ASCII RAW files
    * Fixed Issue #140 and #131 - Compatibility with LTspice 24+
    * Fixed Issue #145 - Allow easy hiding of simulator's console message
    * Fixed Issue #137 - More default library paths
    * Fixed Issue #130 - allow .cir files in QspiceLogReader
    * Fixed Issue #129 - Hiearchical Schematic in QSpice (.qsch)
    * Fixed issue with alias finding in RawRead
    * Fixed Issue #122 - QSpice netlist generation when component designator is not aligned with prefix
    * Minor issues in the examples
* Version 1.3.6
    * Fixed Issue #127 - Points on PARAM values
* Version 1.3.5
    * Issue #124 Fixed - Problem with .PARAM regex.
    * Using Poetry for generating the wheel packages
* Version 1.3.4
    * Issue #120 Fixed
* Version 1.3.3
    * Minor documentation fixes
* Version 1.3.2
    * Documenting the user library paths
    * AscEditor: Adding support to DATAFLAG
    * LTSteps: Supporting new LTspice data export format
    * Fix Issue #116: PosixPath as no lower attribute
    * Toolkit:
        * Correction on the WCA min max formula and adding the run < 0 condition
        * run_testbench can be called without having to call first save_netlist
* Version 1.3.1
    * Adding possibility of manipulating parameters on sub-circuits
    * Supporting subcircuit names with dots.
    * Overall documentation improvements (thanks @hb020)
    * Fix: Inclusion of encrypted libraries would crash
* Version 1.3.0
    * Major improvement in Documentation
    * Introduced a read-only property that blocks libraries from being updated.
    * Support for LTspice log files with the option : expanded netlist
    * Supporting library symbols using BLOCK primitive
    * Improved unittest on the .ASC hierarchical design
    * SimRunner simulation iterator only returns successful simulations in order to simplify error management
    * In QschEditor, the replacement of unique dot instructions (ex: .TRAN .AC .NOISE) is only done if the existing
      instruction is not commented.
    * RunTask.get_results() now returns None if a callback function is provided and the simulation has failed.
    * Bugfix: Prefix were case sensitive in SpiceEditor
    * Bugfix: Parsing netlists with extensions other than .net didn't work properly
* Version 1.2.1
    * Fix on the generation of netlists from QSPICE Schematic files.
        * Floating pins are now correctly handled. (Issue #88)
        * Support for all known QSpice components.
        * Improving testbench for the QschEditor.
* Version 1.2.0
    * Implementing a new approach to the accessing component values and parameters. Instead of using the
      get_component_value() and get_component_parameters() methods, the component values and parameters are now accessed
      directly as attributes of the component object. This change was made to make the code more readable.
      The old methods are still available for backward compatibility.
    * Improvements on the documentation.
    * Added testbench for the regular expressions used on the SpiceEditor. Improvements on the regular expressions.
    * Improvements on the usage of spicelib in Linux and MacOS using wine.
* Version 1.1.4
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
    * Restructure the way netlists are read and written, so to be able to read and write netlists from different
      simulator
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
