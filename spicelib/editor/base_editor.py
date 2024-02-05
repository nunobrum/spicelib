#!/usr/bin/env python
# coding=utf-8
import dataclasses
import enum
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

from abc import ABC, abstractmethod
from math import floor, log
from pathlib import Path
from typing import Union, List
from collections import OrderedDict
import logging

_logger = logging.getLogger("spicelib.BaseEditor")

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
PARAM_REGEX = r"(?<= )(?P<replace>%s(\s*=\s*)(?P<value>[\w\*\/\.\+\-\/\*\{\}\(\)\t ]*))(?<!\s)($|\s+)(?!\s*=)"


def format_eng(value) -> str:
    """
    Helper function for formating value with the SI qualifiers.  That is, it will use

        * p for pico (10E-12)
        * n for nano (10E-9)
        * u for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * Meg for Mega (10E+6)


    :param value: float value to format
    :type value: float
    :return: String wiht the formatted value
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
        * Meg for Mega (10E+6)

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
        if suffix[0] in "fpnuµmk":
            return f * {
                'f': 1.0e-15,
                'p': 1.0e-12,
                'n': 1.0e-09,
                'u': 1.0e-06,
                'µ': 1.0e-06,
                'm': 1.0e-03,
                'k': 1.0e+03,
            }[suffix[0]]
        elif suffix.startswith("Meg"):
            return f * 1E+6
    return f


class ComponentNotFoundError(Exception):
    """Component Not Found Error"""


class ParameterNotFoundError(Exception):
    """ParameterNotFound Error"""

    def __init__(self, parameter):
        super().__init__(f'Parameter "{parameter}" not found')


class ERotation(enum.Enum):
    """Component Rotation Enum"""
    R0 = "0 Rotation"
    R90 = "90 Rotation"
    R180 = "180 Rotation"
    R270 = "270 Rotation"
    M0 = "Mirror 0 Rotation"
    M90 = "Mirror 90 Rotation"
    M180 = "Mirror 180 Rotation"
    M270 = "Mirror 270 Rotation"


class HorAlign(enum.Enum):
    """Horizontal Alignment Enum"""
    LEFT = "Left"
    RIGHT = "Right"
    CENTER = "Center"


class VerAlign(enum.Enum):
    """Vertical Alignment Enum"""
    TOP = "Top"
    CENTER = "Center"
    BOTTOM = "Bottom"


class TextTypeEnum(enum.IntEnum):
    """Text Type Enum"""
    NULL = enum.auto()
    COMMENT = enum.auto()
    DIRECTIVE = enum.auto()
    LABEL = enum.auto()
    ATTRIBUTE = enum.auto()


@dataclasses.dataclass
class Point:
    """X, Y coordinates"""
    X: int
    Y: int


@dataclasses.dataclass
class Line:
    """X1, Y1, X2, Y2 coordinates"""
    V1: Point
    V2: Point


@dataclasses.dataclass
class Text:
    """Text object"""
    coord: Point
    text: str
    size: int = 1
    type: TextTypeEnum = TextTypeEnum.NULL
    textAlignment: HorAlign = HorAlign.LEFT
    verticalAlignment: VerAlign = VerAlign.CENTER


class SchematicComponent(object):
    """Hols component information"""

    def __init__(self):
        self.position: Point = Point(0, 0)
        self.rotation: ERotation = ERotation.R0
        self.reference = ""
        self.attributes = OrderedDict()
        self.symbol = None


class BaseEditor(ABC):
    """
    This defines the primitives (protocol) to be used for both SpiceEditor and AscEditor
    classes.
    """
    def __init__(self):
        self._components: OrderedDict[str, SchematicComponent] = OrderedDict()
        self._wires: List[Line] = []
        self._labels: List[Text] = []
        self._directives: List[Text] = []

    @property
    @abstractmethod
    def circuit_file(self) -> Path:
        """Returns the netlist as a string"""
        ...

    def reset_netlist(self) -> None:
        """Resets the netlist to the original state"""
        self._components.clear()
        self._wires.clear()
        self._labels.clear()
        self._directives.clear()

    @abstractmethod
    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """Writes the netlist to a file"""
        ...

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        (Deprecated)

        Writes the netlist to a file. This is an alias to save_netlist."""
        self.save_netlist(run_netlist_file)

    @abstractmethod
    def get_component_info(self, component) -> dict:
        """
        Retrieves the component information. The line number is also added.

        :param component: Reference of the component
        :type component: str
        :return: Dictionary with the component information
        :rtype: dict
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX. NotImplementedError of there
                 isn't an associated regular expression for the component prefix.
        """
        ...

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
        subcircuits, use the subcirciut designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            editor.set_component_value('R1', '3.3k')
            editor.set_component_value('X1:C1', '10u')

        :param device: Reference of the circuit element to be updated.
        :type device: str
        :param value:
            value to be be set on the given circuit element. Float and integer values will automatically
            formatted as per the engineering notations 'k' for kilo, 'm', for mili and so on.
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
        """Serves to add SPICE instructions to the simulation netlist. For example:

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
        """Usage a previously added instructions.
        Example: ::

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
        """Removes a list of instructions from the SPICE NETLIST.
        Example:
        ::

            editor.remove_Xinstruction("\.AC.*")

        :param search_pattern: The list of instructions to remove. Each instruction is of the type 'str'
        :type search_pattern: str
        :returns: Nothing
        """
        ...

    def add_instructions(self, *instructions) -> None:
        """Adds a list of instructions to the SPICE NETLIST.
        Example:
        ::

            editor.add_instructions(
                ".STEP run -1 1023 1",
                ".dc V1 -5 5"
            )

        :param instructions: Argument list of instructions to add
        :type instructions: argument list
        :returns: Nothing
        """
        for instruction in instructions:
            self.add_instruction(instruction)
