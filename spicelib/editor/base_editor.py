# coding=utf-8
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        base_editor.py
# Purpose:     Abstract class that defines the protocol for the editors
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__version__ = "0.1.0"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

from abc import ABC, abstractmethod
from collections import OrderedDict
from math import floor, log
from pathlib import Path
from typing import Union, List
import logging
import os
from ..sim.simulator import Simulator


_logger = logging.getLogger("spicelib.BaseEditor")

SUBCKT_DIVIDER = ':'  #: This controls the sub-circuit divider when setting component values inside sub-circuits.
# Ex: Editor.set_component_value('XU1:R1', '1k')

UNIQUE_SIMULATION_DOT_INSTRUCTIONS = ('.AC', '.DC', '.TRAN', '.NOISE', '.DC', '.TF')
SPICE_DOT_INSTRUCTIONS = (
    '.BACKANNO',
    '.END',
    '.ENDS',
    '.FERRET',  # Downloads a File from a given URL
    '.FOUR',  # Compute a Fourier Component after a .TRAN Analysis
    '.FUNC', '.FUNCTION',
    '.GLOBAL',
    '.IC',
    '.INC', '.INCLUDE',  # Include another file
    '.LIB',  # Include a Library
    '.LOADBIAS',  # Load a Previously Solved DC Solution
    # These Commands are part of the contraption Programming Language of the Arbitrary State Machine
    '.MACHINE', '.STATE', '.RULE', '.OUTPUT', '.ENDMACHINE',
    '.MEAS', '.MEASURE',
    '.MODEL',
    '.NET',  # Compute Network Parameters in a .AC Analysis
    '.NODESET',  # Hints for Initial DC Solution
    '.OP',
    '.OPTIONS',
    '.PARAM', '.PARAMS',
    '.SAVE', '.SAV',
    '.SAVEBIAS',
    '.STEP',
    '.SUBCKT',
    '.TEXT',
    '.WAVE',  # Write Selected Nodes to a .Wav File

)


def PARAM_REGEX(pname):
    return r"(?P<name>" + pname + r")\s*[= ]\s*(?P<value>(?P<cb>\{)?(?(cb)[^\}]*\}|[\d\.\+\-Ee]+[a-zA-Z%]*))"


def format_eng(value) -> str:
    """
    Helper function for formatting value with the SI qualifiers.  That is, it will use

        * p for pico (10E-12)
        * n for nano (10E-9)
        * u for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * Meg for Mega (10E+6)
        * g for giga (10E+9)
        * t for tera (10E+12)


    :param value: float value to format
    :type value: float
    :return: String with the formatted value
    :rtype: str
    """
    if value == 0.0:
        return "{:g}".format(value)  # This avoids a problematic log(0), and the int and float conversions
    e = floor(log(abs(value), 1000))
    if -5 <= e < 0:
        suffix = "fpnum"[e]
    elif e == 0:
        return "{:g}".format(value)
    elif e == 1:
        suffix = "k"
    elif e == 2:
        suffix = 'Meg'
    elif e == 3:
        suffix = 'g'
    elif e == 4:
        suffix = 't'
    else:
        return '{:E}'.format(value)
    return '{:g}{:}'.format(value * 1000 ** -e, suffix)


def scan_eng(value: str) -> float:
    """
    Converts a string to a float, considering SI multipliers

        * f for femto (10E-15)
        * p for pico (10E-12)
        * n for nano (10E-9)
        * u or µ for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * meg for Mega (10E+6)
        * g for giga (10E+9)
        * t for tera (10E+12)
        
    The extra unit qualifiers such as V for volts or F for Farads are ignored.


    :param value: string to be converted to float
    :type value: str
    :return:
    :rtype: float
    :raises: ValueError when the value cannot be converted.
    """
    # Search for the last digit on the string. Assuming that all after the last number are SI qualifiers and units.
    value = value.strip()
    x = len(value)
    while x > 0:
        if value[x - 1] in "0123456789":
            break
        x -= 1
    suffix = value[x:]  # this is the non-numeric part at the end
    f = float(value[:x])  # this is the numeric part. Can raise ValueError.
    if suffix:
        suffix = suffix.lower()
        # By industry convention, SPICE is not case sensitive
        if suffix.startswith("meg"):
            return f * 1E+6
        elif suffix[0] in "fpnuµmkgt":
            return f * {
                'f': 1.0e-15,
                'p': 1.0e-12,
                'n': 1.0e-09,
                'u': 1.0e-06,
                'µ': 1.0e-06,
                'm': 1.0e-03,
                'k': 1.0e+03,
                'g': 1.0e+09,
                't': 1.0e+12,
            }[suffix[0]]
    return f


def to_float(value, accept_invalid: bool = True) -> Union[float, str]:
    _MULT = {
        'f': 1E-15,
        'p': 1E-12,
        'n': 1E-9,
        'µ': 1E-6,
        'u': 1E-6,
        'U': 1E-6,
        'm': 1E-3,
        'M': 1E-3,
        'k': 1E+3,
        'K': 1E+3,  # For much of the world, K is the same as k. That is a sad fact of life. K is Kelvin in SI
        'Meg': 1E+6,
        'g': 1E+9,
        't': 1E+12,
        # These units can be used as decimal points in the number definition. Ex: 10R5 is 10.5 Ohms. In LTSpice
        # the units can be used in any number definition. For example 10H5 is 10.5 Henrys but also can be used in
        # resistors value definition. LTSpice doesn't care about the unit in the component value definition.
        'Ω': 1,  # This is the Ohm symbol. It is supported by LTspice
        'R': 1,  # This also represents the Ohm symbol. Can be used a decimal point. Ex: 10R2 is 10.2 Ohms
        'V': 1,  # Volts
        'A': 1,  # Amperes (Current)
        'F': 1,  # Farads (Capacitance)
        'H': 1,  # Henry (Inductance)
        '%': 0.01,  # Percent. 10% is 0.1. 1%6 is 0.016
    }

    value = value.strip()  # Removing trailing and leading spaces
    length = len(value)

    multiplier = 1.0

    i = 0
    while i < length and (value[i] in "0123456789.+-"):  # Includes spaces
        i += 1
    if i == 0:
        if accept_invalid:
            return value
        else:
            raise ValueError("Doesn't start with a number")

    if 0 < i < length and (value[i] == 'E' or value[i] == 'e'):
        # if it is a number in scientific format, it doesn't have 1000x qualifiers (Ex: p, u, k, etc...)
        i += 1
        while i < length and (value[i] in "0123456789+-"):  # Includes spaces
            i += 1
        j = k = i
    else:
        # this first part should be able to be converted into float
        k = i  # Stores the position of the end of the number
        # Consume any spaces that may exist between the number and the unit
        while i < length and (value[i] in " \t"):
            i += 1

        if i < length:  # Still has characters to consume
            if value[i] in _MULT:
                if value[i:].upper().startswith('MEG'):  # to 1E+06 qualifier 'Meg'
                    i += 3
                    multiplier = _MULT['Meg']
                else:
                    multiplier = _MULT[value[i]]
                    i += 1

            # This part is done to support numbers with the format 1k7 or 1R8
            j = i
            while i < length and (value[i] in "0123456789"):
                i += 1
        else:
            j = i

    try:
        if j < i:  # There is a suffix number
            value = float(value[:k] + "." + value[j:i]) * multiplier
        else:
            value = float(value[:k]) * multiplier
    except ValueError as err:
        if not accept_invalid:
            raise err
    return value


class ComponentNotFoundError(Exception):
    """Component Not Found Error"""


class ParameterNotFoundError(Exception):
    """ParameterNotFound Error"""

    def __init__(self, parameter):
        super().__init__(f'Parameter "{parameter}" not found')


class Primitive(object):
    """Holds the information of a primitive element in the netlist. This is a base class for the Component and is
    used to hold the information of the netlist primitives, such as .PARAM, .OPTIONS, .IC, .NODESET, .GLOBAL, etc.
    """

    def __init__(self, line: str):
        self.line = line

    def append(self, line):
        """:meta private:"""
        self.line += line

    def __str__(self):
        return self.line


class Component(Primitive):
    """Holds component information"""

    def __init__(self, parent, line: str):
        super().__init__(line)
        self.reference = ""
        self.attributes = OrderedDict()
        self.ports = []
        self.parent = parent

    @property
    def value_str(self) -> str:
        """The Value as a string

        :getter: Returns the value as a string
        :setter: Sets the value. This behaves like the `set_component_value()` method of the editor, but it is more convenient to use when dealing with a single component.

        """        
        return self.parent.get_component_value(self.reference)

    @value_str.setter
    def value_str(self, value):
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")        
        self.parent.set_component_value(self.reference, value)

    @property
    def params(self) -> OrderedDict:
        """Gets all parameters to the component 
        
        This behaves like the `get_component_parameters()` method of the editor, but it is more convenient to use when dealing with a single component.
        """
        return self.parent.get_component_parameters(self.reference)

    def set_params(self, **param_dict):
        """Adds one or more parameters to the component 
        
        The argument is in the form of a key-value pair where each parameter is the key and the value is value to be set in the netlist.
        
        This behaves like the `set_component_parameters()` method of the editor, but it is more convenient to use when dealing with a single component.

        :raises ValueError: If the component is read only, as when it comes from a library
        """
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")           
        self.parent.set_component_parameters(self.reference, **param_dict)

    @property
    def value(self) -> Union[float, int, str]:
        """The Value

        :getter: Returns the value as a number. If the value is not a number, it will return a string.
        :setter: Sets the value.

        """
        return to_float(self.value_str, accept_invalid=True)

    @property
    def model(self) -> str:
        """The model of the component

        :getter: Returns the model of the component
        :setter: Sets the model. This behaves like the `set_element_model()` method of the editor, but it is more convenient to use when dealing with a single component.
 
        """
        return self.parent.get_element_value(self.reference)

    @model.setter
    def model(self, model: str):
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")   
        self.parent.set_element_model(self.reference, model)

    @value.setter
    def value(self, value: Union[str, int, float]):
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")
        if isinstance(value, (int, float)):
            self.value_str = format_eng(value)
        else:
            self.value_str = value

    def __str__(self):
        return f"{self.reference} = {self.value}"

    def __getitem__(self, item):
        return self.attributes[item]

    def __setitem__(self, key, value):
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")        
        self.attributes[key] = value


class BaseEditor(ABC):
    """
    This defines the primitives (protocol) to be used for both SpiceEditor and AscEditor
    classes.
    """
    custom_lib_paths: List[str] = []
    """The custom library paths. Not to be modified, only set via `set_custom_library_paths()`.
    This is a class variable, so it will be shared between all instances
    
    :meta hide-value:"""    
    simulator_lib_paths: List[str] = []
    """ This is initialised with typical locations found for your simulator.
    You can (and should, if you use wine), call `prepare_for_simulator()` once you've set the executable paths.
    This is a class variable, so it will be shared between all instances.
    
    :meta hide-value:
    """

    @property
    @abstractmethod
    def circuit_file(self) -> Path:
        """Returns the path of the circuit file."""
        ...

    @abstractmethod
    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist will be reset to a new empty netlist. If False, the netlist will be
                             reset to the original state.
        """
        ...

    @abstractmethod
    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        Saves the current state of the netlist to a file.

        :param run_netlist_file: File name of the netlist file.
        :type run_netlist_file: Path or str
        :returns: Nothing
        """
        ...

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        .. deprecated:: 1.x Use `save_netlist()` instead.

        Writes the netlist to a file. This is an alias to save_netlist."""
        self.save_netlist(run_netlist_file)

    @abstractmethod
    def get_component(self, reference: str) -> Component:
        """Returns the Component object representing the given reference in the netlist."""
        ...

    @abstractmethod
    def get_subcircuit(self, reference: str) -> 'BaseEditor':
        """Returns a hierarchical subdesign"""
        ...

    def __getitem__(self, item) -> Component:
        """
        This method allows the user to get the value of a component using the syntax:
        component = circuit['R1']
        """
        return self.get_component(item)

    def __setitem__(self, key, value):
        self.set_component_value(key, value)

    def get_component_attribute(self, reference: str, attribute: str) -> str:
        """
        Returns the value of the attribute of the component. Attributes are the values that are not related with
        SPICE parameters. For example, component manufacturer, footprint, schematic appearance, etc.
        User can define whatever attributes they want. The only restriction is that the attribute name must be a string.
        
        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute being sought
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the attribute is not found
        """
        return self.get_component(reference).attributes[attribute]

    def get_component_nodes(self, reference: str) -> list:
        """Returns the value of the port of the component.
        
        :param reference: Reference of the component
        :type reference: str
        :return: List with the ports of the component
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the port is not found
        
        """
        return self.get_component(reference).ports

    @abstractmethod
    def get_parameter(self, param: str) -> str:
        """
        Retrieves a Parameter from the Netlist

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """
        ...
        
    @abstractmethod
    def get_all_parameter_names(self, param: str) -> str:
        """
        Returns all parameter names from the netlist.

        :return: A list of parameter names found in the netlist
        :rtype: List[str]
        """
        ...        

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        """Adds a parameter to the SPICE netlist.

        Usage: ::

         editor.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in it's usage,
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        ...

    def set_parameters(self, **kwargs):
        """Adds one or more parameters to the netlist.
        Usage: ::

            for temp in (-40, 25, 125):
                for freq in sweep_log(1, 100E3,):
                    editor.set_parameters(TEMP=80, freq=freq)

        :key param_name:
            Key is the parameter to be set. values the ther corresponding values. Values can either be a str; an int or
            a float.

        :returns: Nothing
        """
        for param in kwargs:
            self.set_parameter(param, kwargs[param])

    @abstractmethod
    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        """Changes the value of a component, such as a Resistor, Capacitor or Inductor. For components inside
        sub-circuits, use the sub-circuit designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            editor.set_component_value('R1', '3.3k')
            editor.set_component_value('X1:C1', '10u')

        :param device: Reference of the circuit element to be updated.
        :type device: str
        :param value:
            value to be set on the given circuit element. Float and integer values will automatically
            formated as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        ...

    @abstractmethod
    def set_element_model(self, element: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            editor.set_element_model('D1', '1N4148')
            editor.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

        :param element: Reference of the circuit element to be updated.
        :type element: str
        :param model: model name of the device to be updated
        :type model: str

        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the model format contains irregular characters

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        ...

    @abstractmethod
    def set_component_parameters(self, element: str, **kwargs) -> None:
        """
        Adds one or more parameters to the component on the netlist. The argument is in the form of a key-value pair
        where each parameter is the key and the value is value to be set in the netlist.

        Usage 1: ::

         editor.set_component_parameters(R1, value=330, temp=25)

        Usage 2: ::

         value_settings = {'value': 330, 'temp': 25}
         editor.set_component_parameters(R1, **value_settings)

        :param element: Reference of the circuit element.
        :type element: str

        :key <param_name>:
            The key is the parameter name and the value is the value to be set. Values can either be
            strings; integers or floats. When None is given, the parameter will be removed, if possible.

        :return: Nothing
        :raises: ComponentNotFoundError - In case one of the component is not found.
        """
        ...

    def set_component_attribute(self, reference: str, attribute: str, value: str) -> None:
        """Sets the value of the attribute of the component. Attributes are the values that are not related with
        SPICE parameters. For example, component manufacturer, footprint, schematic appearance, etc.
        User can define whatever attributes they want. The only restriction is that the attribute name must be a string.
        
        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be set
        :type attribute: str
        :param value: Value of the attribute to be set
        :type value: str
        :return: Nothing
        :raises: ComponentNotFoundError - In case the component is not found
        """
        self.get_component(reference).attributes[attribute] = value

    @abstractmethod
    def get_component_value(self, element: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value.
        :type element: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        ...

    @abstractmethod
    def get_component_parameters(self, element: str) -> dict:
        """
        Returns the parameters of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the parameters.
        :type element: str

        :return: parameters of the circuit element in dictionary format.
        :rtype: dict

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        ...

    def get_component_floatvalue(self, element: str) -> float:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value in float format.
        :type element: str

        :return: value of the circuit element in float type
        :rtype: float

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return scan_eng(self.get_component_value(element))

    def set_component_values(self, **kwargs):
        """
        Adds one or more components on the netlist. The argument is in the form of a key-value pair where each
        component designator is the key and the value is value to be set in the netlist.

        Usage 1: ::

         editor.set_component_values(R1=330, R2="3.3k", R3="1Meg", V1="PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)")

        Usage 2: ::

         value_settings = {'R1': 330, 'R2': '3.3k', 'R3': "1Meg", 'V1': 'PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)'}
         editor.set_component_values(**value_settings)

        :key <comp_ref>:
            The key is the component designator (Ex: V1) and the value is the value to be set. Values can either be
            strings; integers or floats

        :return: Nothing
        :raises: ComponentNotFoundError - In case one of the component is not found.
        """
        for value in kwargs:
            self.set_component_value(value, kwargs[value])

    @abstractmethod
    def get_components(self, prefixes='*') -> list:
        """
        Returns a list of components that match the list of prefixes indicated on the parameter prefixes.
        In case prefixes is left empty, it returns all the ones that are defined by the REPLACE_REGEXES.
        The list will contain the designators of all components found.

        :param prefixes:
            Type of prefixes to search for. Examples: 'C' for capacitors; 'R' for Resistors; etc... See prefixes
            in SPICE documentation for more details.
            The default prefix is '*' which is a special case that returns all components.
        :type prefixes: str

        :return:
            A list of components matching the prefixes demanded.
        """
        ...

    @abstractmethod
    def add_component(self, component: Component, **kwargs) -> None:
        """
        Adds a component to the design. If the component already exists, it will be replaced by the new one.
        kwargs are implementation specific and can be used to pass additional information to the implementation.

        :param component: Component to be added to the design.
        :type component: Component

        :return: Nothing
        """
        ...

    @abstractmethod
    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design.
        Note: Current implementation only allows removal of a component from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        ...

    @abstractmethod
    def add_instruction(self, instruction: str) -> None:
        """
        Adds a SPICE instruction to the netlist.

        For example:

            .. code-block:: text

                .tran 10m ; makes a transient simulation
                .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms" ; Establishes a measuring
                .step run 1 100, 1 ; makes the simulation run 100 times

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        ...

    @abstractmethod
    def remove_instruction(self, instruction) -> None:
        """
        Removes a SPICE instruction from the netlist.

        Example:
        
        .. code-block:: python
                
            editor.remove_instruction(".STEP run -1 1023 1")

        This only works if the instruction exactly matches the line on the netlist. This means that space characters,
        and upper case and lower case differences will not match the line.

        :param instruction: The list of instructions to remove. Each instruction is of the type 'str'
        :type instruction: str
        :returns: Nothing
        """
        ...

    @abstractmethod
    def remove_Xinstruction(self, search_pattern: str) -> None:
        """
        Removes a SPICE instruction from the netlist based on a search pattern. This is a more flexible way to remove
        instructions from the netlist. The search pattern is a regular expression that will be used to match the
        instructions to be removed. The search pattern will be applied to each line of the netlist and if the pattern
        matches, the line will be removed.

        Example: The code below will remove all AC analysis instructions from the netlist.

        .. code-block:: python

            editor.remove_Xinstruction("\\.AC.*")

        :param search_pattern: The list of instructions to remove. Each instruction is of the type 'str'
        :type search_pattern: str
        :returns: Nothing
        """
        ...

    def add_instructions(self, *instructions) -> None:
        """
        Adds a list of instructions to the SPICE NETLIST.
        
        Example:
        
        .. code-block:: python

            editor.add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")
        
        :param instructions: Argument list of instructions to add
        :type instructions: argument list
        :returns: Nothing        
        """

        for instruction in instructions:
            self.add_instruction(instruction)
       
    @classmethod     
    def prepare_for_simulator(cls, simulator: Simulator) -> None:
        """
        Sets the library paths that should be correct for the simulator object. 
        The simulator object should have had the executable path (spice_exe) set correctly.
        
        This is especially useful in 2 cases:
            * when the simulator is running under wine, as it is difficult to detect \
                the correct library paths in that case.
            * when the editor can be used with different simulators, that have different library paths.
        
        Note:
            * you can always also set the library paths manually via `set_custom_library_paths()`
            * this method is a class method and will affect all instances of the class

        :param simulator: Simulator object from which the library paths will be taken.
        :type simulator: Simulator
        :returns: Nothing
        """
        if simulator is None:
            raise NotImplementedError("The prepare_for_simulator method requires a simulator object")
        cls.simulator_lib_paths = simulator.get_default_library_paths()
        return
    
    @classmethod
    def _check_and_append_custom_library_path(cls, path) -> None:
        """:meta private:"""
        if path.startswith("~"):
            path = os.path.expanduser(path)
            
        if os.path.exists(path) and os.path.isdir(path):
            _logger.debug(f"Adding path '{path}' to the custom library path list")
            cls.custom_lib_paths.append(path)
        else:
            _logger.warning(f"Cannot add path '{path}' to the custom library path list, as it does not exist")            

    @classmethod
    def set_custom_library_paths(cls, *paths) -> None:
        """
        Set the given library search paths to the list of directories to search when needed.
        It will delete any previous list of custom paths, but will not affect the default paths 
        (be it from `init()` or from `prepare_for_simulator()`).
        
        Note that this method is a class method and will affect all instances of the class.

        :param paths: Path(s) to add to the Search path
        :return: Nothing    
        """
        # empty the list
        cls.custom_lib_paths = []
        # and then fill it with the new paths
        for path in paths:
            if isinstance(path, str):
                cls._check_and_append_custom_library_path(path)
            elif isinstance(path, list):
                for p in path:
                    cls._check_and_append_custom_library_path(p)
            
    def is_read_only(self) -> bool:
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        return False


class HierarchicalComponent(object):
    """Helper class to allow setting parameters when using object oriented access."""

    def __init__(self, component: Component, parent: BaseEditor, reference: str):
        self._component = component
        self._parent = parent
        self._reference = reference

    def __getattr__(self, attr):
        return getattr(self._component, attr)

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            self.__dict__[attr] = value
        elif attr in ("value", "value_str"):
            self._parent.set_component_value(self._reference, value)
        elif attr == "params":
            if not isinstance(value, dict):
                raise ValueError("Expecting value to be a dictionary type")
            self._parent.set_component_parameters(self._reference, **value)
        else:
            setattr(self._component, attr, value)
