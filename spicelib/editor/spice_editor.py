#!/usr/bin/env python
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
# Name:        spice_editor.py
# Purpose:     Class made to update Generic Spice netlists
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import os
from collections import OrderedDict
from pathlib import Path
import re
import logging

from .base_editor import BaseEditor, format_eng, ComponentNotFoundError, ParameterNotFoundError, PARAM_REGEX, \
    UNIQUE_SIMULATION_DOT_INSTRUCTIONS, Component, SUBCKT_DIVIDER, HierarchicalComponent

from typing import Union, List, Callable, Any, Tuple, Optional
from ..utils.detect_encoding import detect_encoding, EncodingDetectError
from ..utils.file_search import search_file_in_containers
from ..log.logfile_data import try_convert_value
from ..simulators.ltspice_simulator import LTspice

_logger = logging.getLogger("spicelib.SpiceEditor")

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

END_LINE_TERM = '\n'  #: This controls the end of line terminator used

# A Spice netlist can only have one of the instructions below, otherwise an error will be raised

# Regular expressions for the different components
FLOAT_RGX = r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"

# Regular expression for a number with decimal qualifier and unit
NUMBER_RGX = r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?(Meg|[kmuµnpfgt])?[a-zA-Z]*"

# Parameters expression of the type: PARAM=value
PARAM_RGX = r"(?P<params>(\s+\w+\s*(=\s*[\w\{\}\(\)\-\+\*\/%\.]+)?)*)?"


def VALUE_RGX(number_regex):
    """Named Regex for a value or a formula."""
    return r"(?P<value>(?P<formula>{)?(?(formula).*}|" + number_regex + "))"


REPLACE_REGEXS = {
    'A': r"",  # LTspice Only : Special Functions, Parameter substitution not supported
    'B': r"^(?P<designator>B§?[VI]?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Behavioral source
    'C': r"^(?P<designator>C§?\w+)(?P<nodes>(\s+\S+){2})(?P<model>\s+\w+)?\s+" +
         VALUE_RGX(FLOAT_RGX + r"[muµnpfgt]?F?") +
         PARAM_RGX + r".*?$",  # Capacitor
    'D': r"^(?P<designator>D§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>\w+)" +
         PARAM_RGX + ".*?$",  # Diode
    'E': r"^(?P<designator>E§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>.*)$",  # Voltage Dependent Voltage Source
    # this only supports changing gain values
    'F': r"^(?P<designator>F§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Current Dependent Current Source
    # This implementation replaces everything after the 2 first nets
    'G': r"^(?P<designator>G§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>.*)$",  # Voltage Dependent Current Source
    # This only supports changing gain values
    'H': r"^(?P<designator>H§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Voltage Dependent Current Source
    # This implementation replaces everything after the 2 first nets
    'I': r"^(?P<designator>I§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*?)"
         r"(?P<params>(\s+\w+\s*=\s*[\w\{\}\(\)\-\+\*\/%\.]+)*)$",  # Independent Current Source
    # This implementation replaces everything after the 2 first nets
    'J': r"^(?P<designator>J§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>\w+)" + 
         PARAM_RGX + ".*?$",  # JFET
    'K': r"^(?P<designator>K§?\w+)(?P<nodes>(\s+\S+){2,4})\s+(?P<value>[\+\-]?[0-9\.E+-]+[kmuµnpgt]?).*$",  # Mutual Inductance
    'L': r"^(?P<designator>L§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>({)?(?(5).*}|([0-9\.E+-]+(Meg|[kmuµnpgt])?H?))).*$",  # Inductance
    'M': r"^(?P<designator>M§?\w+)(?P<nodes>(\s+\S+){3,4})\s+(?P<value>\w+)" + PARAM_RGX + ".*?$",  # MOSFET
    'O': r"^(?P<designator>O§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>\w+)" + PARAM_RGX + ".*?$",  # Lossy Transmission Line
    'Q': r"^(?P<designator>Q§?\w+)(?P<nodes>(\s+\S+){3,4})\s+(?P<value>\w+)" + PARAM_RGX + ".*?$",  # Bipolar
    'R': r"^(?P<designator>R§?\w+)(?P<nodes>(\s+\S+){2})(?P<model>\s+\w+)?\s+" +
         "(R=)?" + VALUE_RGX(FLOAT_RGX + r"(Meg|[kRmuµnpfgt])?\d*") +
         PARAM_RGX + ".*?$",  # Resistor
    'S': r"^(?P<designator>S§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>.*)$",  # Voltage Controlled Switch
    'T': r"^(?P<designator>T§?\w+)(?P<nodes>(\s+\S+){4})\s+(?P<value>.*)$",  # Lossless Transmission
    'U': r"^(?P<designator>U§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>.*)$",  # Uniform RC-line
    'V': r"^(?P<designator>V§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*?)"
         r"(?P<params>(\s+\w+\s*=\s*[\w\{\}\(\)\-\+\*\/%\.]+)*)$",  # Independent Voltage Source
    # ex: V1 NC_08 NC_09 PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) AC 1 2 Rser=3 Cpar=4
    'W': r"^(?P<designator>W§?\w+)(?P<nodes>(\s+\S+){2})\s+(?P<value>.*)$",  # Current Controlled Switch
    # This implementation replaces everything after the 2 first nets
    'X': r"^(?P<designator>X§?\w+)(?P<nodes>(\s+\S+){1,99})\s+(?P<value>[\w\.]+)"
         r"(\s+params:)?" + PARAM_RGX + r"\\?$",  # Sub-circuit. The value is the last before any key-value parameters
    # This is structured differently than the others as it will accept any number of nodes.
    # But it only supports 1 value without any spaces in it (unlike V for example).
    # ex: XU1 NC_01 NC_02 NC_03 NC_04 NC_05 level2 Avol=1Meg GBW=10Meg Slew=10Meg Ilimit=25m Rail=0 Vos=0 En=0 Enk=0 In=0 Ink=0 Rin=500Meg
    #     XU1 in out1 -V +V out1 OPAx189 bla_v2 =1% bla_sp1=1 bla_sp2 = 1
    #     XU1 in out1 -V +V out1 GND OPAx189_float
    'Z': r"^(?P<designator>Z§?\w+)(?P<nodes>(\s+\S+){3})\s+(?P<value>\w+).*$",

    # MESFET and IBGT. TODO: Parameters substitution not supported
    '@': r"^(?P<designator>@§?\d+)(?P<nodes>(\s+\S+){2})\s?(?P<params>(.*)*)$",
    # Frequency Noise Analysis (FRA) wiggler
    # pattern = r'^@(\d+)\s+(\w+)\s+(\w+)(?:\s+delay=(\d+\w+))?(?:\s+fstart=(\d+\w+))?(?:\s+fend=(\d+\w+))?(?:\s+oct=(\d+))?(?:\s+fcoarse=(\d+\w+))?(?:\s+nmax=(\d+\w+))?\s+(\d+)\s+(\d+\w+)\s+(\d+)(?:\s+pp0=(\d+\.\d+))?(?:\s+pp1=(\d+\.\d+))?(?:\s+f0=(\d+\w+))?(?:\s+f1=(\d+\w+))?(?:\s+tavgmin=(\d+\w+))?(?:\s+tsettle=(\d+\w+))?(?:\s+acmag=(\d+))?$'
    'Ã': r"^(?P<designator>Ã\w+)(?P<nodes>(\s+\S+){16})\s+(?P<value>.*)" + PARAM_RGX + ".*?$",  # QSPICE Unique component Ã
    '¥': r"^(?P<designator>¥\w+)(?P<nodes>(\s+\S+){16})\s+(?P<value>.*)" + PARAM_RGX + ".*?$",  # QSPICE Unique component ¥
    '€': r"^(?P<designator>€\w+)(?P<nodes>(\s+\S+){32})\s+(?P<value>.*)" + PARAM_RGX + ".*?$",  # QSPICE Unique component €
    '£': r"^(?P<designator>£\w+)(?P<nodes>(\s+\S+){64})\s+(?P<value>.*)" + PARAM_RGX + ".*?$",  # QSPICE Unique component £
    'Ø': r"^(?P<designator>Ø\w+)(?P<nodes>(\s+\S+){1,99})\s+(?P<value>.*)" + PARAM_RGX + ".*?$",  # QSPICE Unique component Ø
    '×': r"^(?P<designator>×\w+)(?P<nodes>(\s+\S+){4,16})\s+(?P<value>.*)(?P<params>(\w+\s+){1,8})\s*\\?$",  # QSPICE proprietaty component ×
    'Ö': r"^(?P<designator>Ö\w+)(?P<nodes>(\s+\S+){5})\s+(?P<params>.*)\s*\\?$",  # LTspice proprietary component Ö
}

SUBCKT_CLAUSE_FIND = r"^.SUBCKT\s+"

# Code Optimization objects, avoiding repeated compilation of regular expressions
component_replace_regexs = {prefix: re.compile(pattern, re.IGNORECASE) for prefix, pattern in REPLACE_REGEXS.items()}
subckt_regex = re.compile(r"^.SUBCKT\s+(?P<name>[\w\.]+)", re.IGNORECASE)
lib_inc_regex = re.compile(r"^\.(LIB|INC)\s+(.*)$", re.IGNORECASE)

# The following variable deprecated, and here only so that people can find it. 
# It is replaced by SpiceEditor.set_custom_library_paths().
# Since I cannot keep it operational easily, I do not use the deprecated decorator or the magic from https://stackoverflow.com/a/922693.
#
# LibSearchPaths = []


def get_line_command(line) -> str:
    """
    Retrives the type of SPICE command in the line.
    Starts by removing the leading spaces and the evaluates if it is a comment, a directive or a component.
    """
    if isinstance(line, str):
        for i in range(len(line)):
            ch = line[i]
            if ch == ' ' or ch == '\t':
                continue
            else:
                ch = ch.upper()
                if ch in REPLACE_REGEXS:  # A circuit element
                    return ch
                elif ch == '+':
                    return '+'  # This is a line continuation.
                elif ch in "#;*\n\r":  # It is a comment or a blank line
                    return "*"
                elif ch == '.':  # this is a directive
                    j = i + 1
                    while j < len(line) and (line[j] not in (' ', '\t', '\r', '\n')):
                        j += 1
                    return line[i:j].upper()
                else:
                    raise SyntaxError(f"Unrecognized command in line: \"{line}\"")
    elif isinstance(line, SpiceCircuit):
        return ".SUBCKT"
    else:
        raise SyntaxError('Unrecognized command in line "{}"'.format(line))


def _first_token_upped(line):
    """
    (Private function. Not to be used directly)
    Returns the first non-space character in the line. If a point '.' is found, then it gets the primitive associated.
    """
    i = 0
    while i < len(line) and line[i] in (' ', '\t'):
        i += 1
    j = i
    while i < len(line) and not (line[i] in (' ', '\t')):
        i += 1
    return line[j:i].upper()


def _is_unique_instruction(instruction):
    """
    (Private function. Not to be used directly)
    Returns true if the instruction is one of the unique instructions
    """
    cmd = get_line_command(instruction)
    return cmd in UNIQUE_SIMULATION_DOT_INSTRUCTIONS


def _parse_params(params_str: str) -> dict:
    """
    Parses the parameters string and returns a dictionary with the parameters.
    """
    params = OrderedDict()
    for param in params_str.split():
        key, value = param.split('=')
        params[key] = try_convert_value(value)
    return params


class UnrecognizedSyntaxError(Exception):
    """Line doesn't match expected Spice syntax"""

    def __init__(self, line, regex):
        super().__init__(f'Line: "{line}" doesn\'t match regular expression "{regex}"')


class MissingExpectedClauseError(Exception):
    """Missing expected clause in Spice netlist"""


class SpiceComponent(Component):
    """
    Represents a SPICE component in the netlist. It allows the manipulation of the parameters and the value of the
    component.
    """

    def __init__(self, parent, line_no):
        line = parent.netlist[line_no]
        super().__init__(parent, line)
        self.parent = parent
        self.update_attributes_from_line_no(line_no)

    def update_attributes_from_line_no(self, line_no: int) -> re.match:
        """Update attributes of a component at a specific line in the netlist

        :param line_no: line in the netlist
        :type line_no: int
        :raises NotImplementedError: When the component type is not recognized
        :raises UnrecognizedSyntaxError: When the line doesn't match the expected REGEX.
        :return: The match found
        :rtype: re.match
        
        :meta private:
        """
        self.line = self.parent.netlist[line_no]
        prefix = self.line[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {self.line}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        match = regex.match(self.line)
        if match is None:
            raise UnrecognizedSyntaxError(self.line, regex.pattern)

        info = match.groupdict()
        self.attributes.clear()
        for attr in info:
            if attr == 'designator':
                self.reference = info[attr]
            elif attr == 'nodes':
                self.ports = info[attr].split()
            elif attr == 'params':
                self.attributes['params'] = _parse_params(info[attr])
            else:
                self.attributes[attr] = info[attr]
        return match

    def update_from_reference(self):
        """:meta private:"""
        line_no = self.parent.get_line_starting_with(self.reference)
        self.update_attributes_from_line_no(line_no)

    @property
    def value_str(self) -> str:
        # docstring inherited from Component
        self.update_from_reference()
        return self.attributes['value']

    @value_str.setter
    def value_str(self, value: Union[str, int, float]):
        # docstring inherited from Component
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")        
        self.parent.set_component_value(self.reference, value)

    def __getitem__(self, item):
        self.update_from_reference()
        try:
            return super().__getitem__(item)
        except KeyError:
            # If the attribute is not found, then it is a parameter
            return self.params[item]

    def __setitem__(self, key, value):
        if self.parent.is_read_only():
            raise ValueError("Editor is read-only")        
        if key == 'value':
            if isinstance(value, str):
                self.value_str = value
            else:
                self.value = value
        else:
            self.set_params(**{key: value})


class SpiceCircuit(BaseEditor):
    """
    Represents sub-circuits within a SPICE circuit. Since sub-circuits can have sub-circuits inside
    them, it serves as base for the top level netlist. This hierarchical approach helps to encapsulate
    and protect parameters and components from edits made at a higher level.
    """
    
    simulator_lib_paths: List[str] = LTspice.get_default_library_paths()    
    """ This is initialised with typical locations found for LTspice.
    You can (and should, if you use wine), call `prepare_for_simulator()` once you've set the executable paths.
    This is a class variable, so it will be shared between all instances.
    
    :meta hide-value:
    """

    def __init__(self, parent: "SpiceCircuit" = None):
        super().__init__()
        self.netlist = []
        self._readonly = False
        self.modified_subcircuits = {}
        self.parent = parent
        
    def get_line_starting_with(self, substr: str) -> int:
        """Internal function. Do not use.
        
        :meta private:
        """
        # This function returns the line number that starts with the substr string.
        # If the line is not found, then -1 is returned.
        substr_upper = substr.upper()
        for line_no, line in enumerate(self.netlist):
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                continue
            line_upcase = _first_token_upped(line)
            if line_upcase == substr_upper:
                return line_no
        error_msg = "line starting with '%s' not found in netlist" % substr
        _logger.error(error_msg)
        raise ComponentNotFoundError(error_msg)

    def _add_lines(self, line_iter):
        """Internal function. Do not use.
        Add a list of lines to the netlist."""
        for line in line_iter:
            cmd = get_line_command(line)
            if cmd == '.SUBCKT':
                sub_circuit = SpiceCircuit(self)
                sub_circuit.netlist.append(line)
                # Advance to the next non nested .ENDS
                finished = sub_circuit._add_lines(line_iter)
                if finished:
                    self.netlist.append(sub_circuit)
                else:
                    return False
            elif cmd == '+':
                assert len(self.netlist) > 0, "ERROR: The first line cannot be starting with a +"
                self.netlist[-1] += line  # Appends to the last line
            elif len(cmd) == 1 and len(line) > 1 and line[1] == '§':
                # strip any §, it is not always present and seems optional, so scrap it
                line = line[0] + line[2:]
                self.netlist.append(line)
            else:
                self.netlist.append(line)
                if cmd[:4] == '.END':  # True for either .END and .ENDS primitives
                    return True  # If a sub-circuit is ended correctly, returns True
        return False  # If a sub-circuit ends abruptly, returns False

    def _write_lines(self, f):
        """Internal function. Do not use."""
        # This helper function writes the contents of sub-circuit to the file f
        for command in self.netlist:
            if isinstance(command, SpiceCircuit):
                command._write_lines(f)
            else:
                # Writes the modified sub-circuits at the end just before the .END clause
                if command.upper().startswith(".ENDS"):
                    # write here the modified sub-circuits
                    for sub in self.modified_subcircuits.values():
                        sub._write_lines(f)
                f.write(command)

    def _get_param_named(self, param_name) -> Tuple[int, Union[re.Match, None]]:
        """
        Internal function. Do not use. Returns a line starting with command and matching the search with the regular
        expression
        """
        search_expression = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        param_name_upped = param_name.upper()
        line_no = 0
        while line_no < len(self.netlist):
            line = self.netlist[line_no]
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                line_no += 1
                continue
            cmd = get_line_command(line)
            if cmd == '.PARAM':
                matches = search_expression.finditer(line)
                for match in matches:
                    if match.group("name").upper() == param_name_upped:
                        return line_no, match
            line_no += 1
        return -1, None  # If it fails, it returns an invalid line number and No match

    def get_all_parameter_names(self) -> List[str]:
        # docstring inherited from BaseEditor
        param_names = []
        search_expression = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        for line in self.netlist:
            cmd = get_line_command(line)
            if cmd == '.PARAM':
                matches = search_expression.finditer(line)
                for match in matches:
                    param_name = match.group('name')
                    param_names.append(param_name.upper())
        return sorted(param_names)

    def get_subcircuit_names(self) -> List[str]:
        """
        Returns a list of the names of the sub-circuits in the netlist.
        
        :return: list of sub-circuit names
        :rtype: List[str]
        """

        subckt_names = []
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):
                subckt_names.append(line.name())
        return subckt_names

    def get_subcircuit_named(self, name: str) -> Optional['SpiceCircuit']:
        """
        Returns the sub-circuit object with the given name.
        
        :param name: name of the subcircuit
        :type name: str
        :return: _description_
        :rtype: _type_
        """

        for line in self.netlist:
            if isinstance(line, SpiceCircuit):
                if line.name() == name:
                    return line
        if self.parent is not None:
            return self.parent.get_subcircuit_named(name)
        return None

    def get_subcircuit(self, instance_name: str) -> 'SpiceCircuit':
        """
        Returns an object representing a Subcircuit. This object can manipulate elements such as the SpiceEditor does.
        
        :param instance_name: Reference of the subcircuit
        :type instance_name: str
        :returns: SpiceCircuit instance
        :rtype: SpiceCircuit
        :raises UnrecognizedSyntaxError: when an spice command is not recognized by spicelib
        :raises ComponentNotFoundError: When the reference was not found
        """
        if SUBCKT_DIVIDER in instance_name:
            subckt_ref, sub_subckts = instance_name.split(SUBCKT_DIVIDER, 1)
        else:
            subckt_ref = instance_name
            sub_subckts = None  # eliminating the code

        if subckt_ref in self.modified_subcircuits:  # See if this was already a modified sub-circuit instance
            return self.modified_subcircuits[subckt_ref]

        line_no = self.get_line_starting_with(subckt_ref)
        sub_circuit_instance = self.netlist[line_no]
        regex = component_replace_regexs['X']  # The sub-circuit instance regex
        m = regex.search(sub_circuit_instance)
        if m:
            subcircuit_name = m.group('value')  # last_token of the line before Params:
        else:
            raise UnrecognizedSyntaxError(sub_circuit_instance, REPLACE_REGEXS['X'])

        # Search for the sub-circuit in the netlist
        sub_circuit = self.get_subcircuit_named(subcircuit_name)
        if sub_circuit is not None:
            if sub_subckts is None:
                return sub_circuit
            else:
                return sub_circuit.get_subcircuit(SUBCKT_DIVIDER.join(sub_subckts))

        # If we reached here is because the subcircuit was not found. Search for it in declared libraries
        sub_circuit = self.find_subckt_in_included_libs(subcircuit_name)

        if sub_circuit:
            if SUBCKT_DIVIDER in instance_name:
                return sub_circuit.get_subcircuit(sub_subckts)
            else:
                return sub_circuit
        else:
            # The search was not successful
            raise ComponentNotFoundError(f'Sub-circuit "{subcircuit_name}" not found')

    def _get_component_line_and_regex(self, reference: str) -> Tuple[int, re.Match]:
        """Internal function. Do not use."""
        prefix = reference[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {reference}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        line_no = self.get_line_starting_with(reference)
        line = self.netlist[line_no]
        match = regex.match(line)
        if match is None:
            raise UnrecognizedSyntaxError(line, regex.pattern)
        return line_no, match

    def _set_component_attribute(self, reference, attribute, value):
        """
        Internal method to set the model and value of a component.
        """

        # Using the first letter of the component to identify what is it
        if reference[0] == 'X' and SUBCKT_DIVIDER in reference:  # Replaces a component inside of a subciruit
            # In this case the sub-circuit needs to be copied so that is copy is modified. A copy is created for each
            # instance of a sub-circuit.
            component_split = reference.split(SUBCKT_DIVIDER)
            subckt_instance = component_split[0]
            # reference = SUBCKT_DIVIDER.join(component_split[1:])
            if subckt_instance in self.modified_subcircuits:  # See if this was already a modified sub-circuit instance
                sub_circuit: SpiceCircuit = self.modified_subcircuits[subckt_instance]
            else:
                sub_circuit_original = self.get_subcircuit(subckt_instance)  # If not will look for it.
                if sub_circuit_original:
                    new_name = sub_circuit_original.name() + '_' + subckt_instance  # Creates a new name with the path appended
                    sub_circuit = sub_circuit_original.clone(new_name=new_name)

                    # Memorize that the copy is relative to that particular instance
                    self.modified_subcircuits[subckt_instance] = sub_circuit
                    # Change the call to the sub-circuit
                    self._set_component_attribute(subckt_instance, 'model', new_name)
                else:
                    raise ComponentNotFoundError(reference)
            # Update the component
            sub_circuit._set_component_attribute(SUBCKT_DIVIDER.join(component_split[1:]), attribute, value)
        else:
            line_no, match = self._get_component_line_and_regex(reference)
            if attribute in ('value', 'model'):
                # They are actually the same thing just the model is not converted.
                if isinstance(value, (int, float)):
                    value = format_eng(value)
                start = match.start('value')
                end = match.end('value')
                line = self.netlist[line_no]
                self.netlist[line_no] = line[:start] + value + line[end:]
            elif attribute == 'params':
                if not isinstance(value, dict):
                    raise ValueError("set_component_parameters() expects to receive a dictionary")
                if match and match.groupdict().get('params'):
                    params_str = match.group('params')
                    params = self._parse_params(params_str)
                else:
                    params = {}

                for key, kvalue in value.items():
                    # format the kvalue
                    if kvalue is None:
                        kvalue_str = None
                    elif isinstance(kvalue, str):
                        kvalue_str = kvalue.strip()
                    else:
                        kvalue_str = f"{kvalue:G}"
                    if kvalue_str is None:
                        # remove those that must disappear
                        if key in params:
                            params.pop(key)
                    else:
                        # create or update
                        params[key] = kvalue_str
                params_str = ' '.join([f'{key}={kvalue}' for key, kvalue in params.items()])
                start = match.start('params')
                end = match.end('params')
                line = self.netlist[line_no]
                self.netlist[line_no] = line[:start] + ' ' + params_str + line[end:]

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist is blanked. That is, all primitives and components are erased.
        :type create_blank: bool
        :returns: None
        """
        self.netlist.clear()

    def clone(self, **kwargs) -> 'SpiceCircuit':
        """
        Creates a new copy of the SpiceCircuit. Changes done at the new copy do not affect the original.

        :key new_name: The new name to be given to the circuit
        :key type new_name: str
        :return: The new replica of the SpiceCircuit object
        :rtype: SpiceCircuit
        """
        clone = SpiceCircuit(self)
        clone.netlist = self.netlist.copy()
        clone.netlist.insert(0, "***** SpiceEditor Manipulated this sub-circuit ****" + END_LINE_TERM)
        clone.netlist.append("***** ENDS SpiceEditor ****" + END_LINE_TERM)
        new_name = kwargs.get('new_name', None)
        if new_name is not None:
            clone.setname(new_name)
        return clone

    def name(self) -> str:
        """
        Returns the name of the Sub-Circuit.

        :rtype: str
        """
        if len(self.netlist):
            for line in self.netlist:
                m = subckt_regex.search(line)
                if m:
                    return m.group('name')
            else:
                raise RuntimeError("Unable to find .SUBCKT clause in subcircuit")
        else:
            raise RuntimeError("Empty Subcircuit")

    def setname(self, new_name: str):
        """
        Renames the sub-circuit to a new name. No check is done to the new name.
        It is up to the user to make sure that the new name is valid.

        :param new_name: The new Name.
        :type new_name: str
        :return: Nothing
        """
        if len(self.netlist):
            lines = len(self.netlist)
            line_no = 0
            while line_no < lines:
                line = self.netlist[line_no]
                m = subckt_regex.search(line)
                if m:
                    # Replacing the name in the SUBCKT Clause
                    start = m.start('name')
                    end = m.end('name')
                    self.netlist[line_no] = line[:start] + new_name + line[end:]
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")

            # This second loop finds the .ENDS clause
            while line_no < lines:
                line = self.netlist[line_no]
                if get_line_command(line) == '.ENDS':
                    self.netlist[line_no] = '.ENDS ' + new_name + END_LINE_TERM
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")
        else:
            # Avoiding exception by creating an empty sub-circuit
            self.netlist.append("* SpiceEditor Created this sub-circuit")
            self.netlist.append('.SUBCKT %s%s' % (new_name, END_LINE_TERM))
            self.netlist.append('.ENDS %s%s' % (new_name, END_LINE_TERM))

    def get_component(self, reference: str) -> Union[SpiceComponent, 'SpiceCircuit']:
        """
        Returns an object representing the given reference in the schematic file.

        :param reference: Reference of the component
        :type reference: str
        :return: The SpiceComponent object or a SpiceSubcircuit in case of hierarchical design
        :rtype: SpiceComponent or SpiceCircuit
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        if SUBCKT_DIVIDER in reference:
            if reference[0] != 'X':  # Replaces a component inside of a subciruit
                raise ComponentNotFoundError("Only subcircuits can have components inside.")
            else:
                # In this case the sub-circuit needs to be copied so that is copy is modified.
                # A copy is created for each instance of a sub-circuit.
                component_split = reference.split(SUBCKT_DIVIDER)
                subckt_ref = component_split[0]

                if subckt_ref in self.modified_subcircuits:  # See if this was already a modified sub-circuit instance
                    subcircuit = self.modified_subcircuits[subckt_ref]
                else:
                    subcircuit = self.get_subcircuit(subckt_ref)

                if len(component_split) > 1:
                    return subcircuit.get_component(SUBCKT_DIVIDER.join(component_split[1:]))
                else:
                    return subcircuit
        else:
            line_no = self.get_line_starting_with(reference)
            return SpiceComponent(self, line_no)

    def __getitem__(self, item) -> Union[Component, HierarchicalComponent]:
        component = super().__getitem__(item)
        if component.parent != self:
            # encapsulate the object in HierarchicalComponent
            return HierarchicalComponent(component, self, item)
        else:
            return component

    def __delitem__(self, key):
        """
        This method allows the user to delete a component using the syntax:
        del circuit['R1']
        """
        self.remove_component(key)

    def __contains__(self, key):
        """
        This method allows the user to check if a component is in the circuit using the syntax:
        'R1' in circuit
        """
        try:
            self.get_component(key)
            return True
        except ComponentNotFoundError:
            return False

    def __iter__(self):
        """
        This method allows the user to iterate over the components in the circuit using the syntax:
        for component in circuit:
            print(component)
        """
        for line_no, line in enumerate(self.netlist):
            if isinstance(line, SpiceCircuit):
                yield from line
            else:
                cmd = get_line_command(line)
                if cmd in REPLACE_REGEXS:
                    yield SpiceComponent(self, line_no)

    def get_component_attribute(self, reference: str, attribute: str) -> Optional[str]:
        """
        Returns the attribute of a component retrieved from the netlist.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        component = self.get_component(reference)
        return component.attributes.get(attribute, None)

    @staticmethod
    def _parse_params(params_str: str) -> dict:
        """
        Parses the parameters string and returns a dictionary with the parameters.
        """
        params = OrderedDict()
        for param in params_str.split():
            key, value = param.split('=')
            params[key] = try_convert_value(value)
        return params

    def get_component_parameters(self, reference: str) -> dict:
        # docstring inherited from BaseEditor
        line_no, match = self._get_component_line_and_regex(reference)
        if match and match.groupdict().get('params'):
            params_str = match.group('params')
            return self._parse_params(params_str)
        else:
            return {}

    def set_component_parameters(self, reference: str, **kwargs) -> None:
        # docstring inherited from BaseEditor
        if self.is_read_only():
            raise ValueError("Editor is read-only")  
        self._set_component_attribute(reference, 'params', kwargs)

    def get_parameter(self, param: str) -> str:
        """
        Returns the value of a parameter retrieved from the netlist.

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """

        line_no, match = self._get_param_named(param)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(param)

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        """Sets the value of a parameter in the netlist. If the parameter is not found, it is added to the netlist.

        Usage: ::

         runner.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in its usage
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")  
        param_line, match = self._get_param_named(param)
        if isinstance(value, (int, float)):
            value_str = format_eng(value)
        else:
            value_str = value
        if match:
            start, stop = match.span('value')
            line: str = self.netlist[param_line]
            self.netlist[param_line] = line[:start] + f"{value_str}" + line[stop:]
        else:
            # Was not found
            # the last two lines are typically (.backano and .end)
            insert_line = len(self.netlist) - 2
            self.netlist.insert(insert_line, f'.PARAM {param}={value_str}  ; Batch instruction' + END_LINE_TERM)

    def set_component_value(self, reference: str, value: Union[str, int, float]) -> None:
        """
        Changes the value of a component, such as a Resistor, Capacitor or Inductor.
        For components inside sub-circuits, use the sub-circuit designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            runner.set_component_value('R1', '3.3k')
            runner.set_component_value('X1:C1', '10u')

        :param reference: Reference of the circuit element to be updated.
        :type reference: str
        :param value:
            value to be set on the given circuit element. Float and integer values will be automatically
            formatted as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        self._set_component_attribute(reference, 'value', value)

    def set_element_model(self, reference: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            runner.set_element_model('D1', '1N4148')
            runner.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

        :param reference: Reference of the circuit element to be updated.
        :type reference: str
        :param model: model name of the device to be updated
        :type model: str

        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the model format contains irregular characters

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")        
        self._set_component_attribute(reference, 'model', model)

    def get_component_value(self, reference: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param reference: Reference of the circuit element to get the value.
        :type reference: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.get_component(reference).value_str

    def get_component_nodes(self, reference: str) -> List[str]:
        """
        Returns the nodes to which the component is attached to.

        :param reference: Reference of the circuit element to get the nodes.
        :type reference: str
        :return: List of nodes
        :rtype: list
        """
        nodes = self.get_component(reference).ports
        return nodes

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
        answer = []
        if prefixes == '*':
            prefixes = ''.join(REPLACE_REGEXS.keys())
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):  # Only gets components from the main netlist,
                # it currently skips sub-circuits
                continue
            tokens = line.split()
            try:
                if tokens[0][0] in prefixes:
                    answer.append(tokens[0])  # Appends only the designators
            except IndexError or TypeError:
                pass
        return answer

    def add_component(self, component: Component, **kwargs) -> None:
        """
        Adds a component to the netlist. The component is added to the end of the netlist,
        just before the .END statement. If the component already exists, it will be replaced by the new one.

        :param component: The component to be added to the netlist
        :type component: Component
        :param kwargs:
            The following keyword arguments are supported:

            * **insert_before** (str) - The reference of the component before which the new component should be inserted.

            * **insert_after** (str) - The reference of the component after which the new component should be inserted.

        :return: Nothing
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")        
        if 'insert_before' in kwargs:
            line_no = self.get_line_starting_with(kwargs['insert_before'])
        elif 'insert_after' in kwargs:
            line_no = self.get_line_starting_with(kwargs['insert_after'])
        else:
            # Insert before backanno instruction
            try:
                line_no = self.netlist.index(
                    '.backanno\n')  # TODO: Improve this. END of line termination could be differnt
            except ValueError:
                line_no = len(self.netlist) - 2

        nodes = " ".join(component.ports)
        model = component.attributes.get('model', 'no_model')
        parameters = " ".join([f"{k}={v}" for k, v in component.attributes.items() if k != 'model'])
        component_line = f"{component.reference} {nodes} {model} {parameters}{END_LINE_TERM}"
        self.netlist.insert(line_no, component_line)

    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design. Current implementation only allows removal of a component
        from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")        
        line = self.get_line_starting_with(designator)
        self.netlist[line] = ''  # Blanks the line

    @staticmethod
    def add_library_search_paths(*paths) -> None:
        """
        .. deprecated:: 1.1.4 Use the class method `set_custom_library_paths()` instead.
        
        Adds search paths for libraries. By default, the local directory and the
        ~username/"Documents/LTspiceXVII/lib/sub will be searched forehand. Only when a library is not found in these
        paths then the paths added by this method will be searched.

        :param paths: Path to add to the Search path
        :type paths: str
        :return: Nothing
        """
        SpiceCircuit.set_custom_library_paths(*paths)

    def get_all_nodes(self) -> List[str]:
        """
        Retrieves all nodes existing on a Netlist.

        :returns: Circuit Nodes
        :rtype: list[str]
        """
        circuit_nodes = []
        for line in self.netlist:
            prefix = get_line_command(line)
            if prefix in component_replace_regexs:
                match = component_replace_regexs[prefix].match(line)
                if match:
                    nodes = match.group('nodes').split()  # This separates by all space characters including \t
                    for node in nodes:
                        if node not in circuit_nodes:
                            circuit_nodes.append(node)
        return circuit_nodes

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        # docstring is in the parent class
        pass

    def add_instruction(self, instruction: str) -> None:
        # docstring is in the parent class
        pass

    def remove_instruction(self, instruction: str) -> None:
        # docstring is in the parent class
        pass

    def remove_Xinstruction(self, search_pattern: str) -> None:
        # docstring is in the parent class
        pass

    @property
    def circuit_file(self) -> Path:
        """
        Returns the path of the circuit file. Always returns an empty Path for SpiceCircuit.
        """
        return Path('')
    
    def is_read_only(self) -> bool:
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        return self._readonly    

    @staticmethod
    def find_subckt_in_lib(library: str, subckt_name: str) -> Union['SpiceCircuit', None]:
        """
        Finds a sub-circuit in a library. The search is case-insensitive.

        :param library: path to the library to search
        :type library: str
        :param subckt_name: sub-circuit to search for
        :type subckt_name: str
        :return: Returns a SpiceCircuit instance with the sub-circuit found or None if not found
        :rtype: SpiceCircuit
        :meta private:
        """
        # 0. Setup things
        reg_subckt = re.compile(SUBCKT_CLAUSE_FIND + subckt_name, re.IGNORECASE)
        # 1. Find Encoding
        try:
            encoding = detect_encoding(library)
        except EncodingDetectError:
            return None
        #  2. scan the file
        with open(library, encoding=encoding) as lib:
            for line in lib:
                search = reg_subckt.match(line)
                if search:
                    sub_circuit = SpiceCircuit()
                    sub_circuit.netlist.append(line)
                    # Advance to the next non nested .ENDS
                    finished = sub_circuit._add_lines(lib)
                    if finished:
                        # if this is from a lib, don't allow modifications
                        sub_circuit._readonly = True
                        return sub_circuit
        #  3. Return an instance of SpiceCircuit
        return None

    def find_subckt_in_included_libs(self, subcircuit_name: str) -> Optional["SpiceCircuit"]:
        """Find the subcircuit in the list of libraries

        :param subckt_name: sub-circuit to search for
        :type subckt_name: str
        :return: Returns a SpiceCircuit instance with the sub-circuit found or None if not found
        :rtype: SpiceCircuit
        :meta private:
        """
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                continue
            m = lib_inc_regex.match(line)
            if m:  # If it is a library include
                lib = m.group(2)
                lib_filename = search_file_in_containers(lib,
                                                         os.path.split(self.circuit_file)[0],
                                                         # The directory where the file is located
                                                         os.path.curdir,  # The current script directory,
                                                         *self.simulator_lib_paths,  # The simulator's library paths
                                                         *self.custom_lib_paths)  # The custom library paths
                if lib_filename:
                    sub_circuit = SpiceEditor.find_subckt_in_lib(lib_filename, subcircuit_name)
                    if sub_circuit:
                        # Success we can go out
                        # by the way, this circuit will have been marked as readonly
                        return sub_circuit
        if self.parent is not None:
            # try searching on parent netlists
            return self.parent.find_subckt_in_included_libs(subcircuit_name)
        else:
            return None


class SpiceEditor(SpiceCircuit):
    """
    Provides interfaces to manipulate SPICE netlist files. The class doesn't update the netlist file
    itself. After implementing the modifications the user should call the "save_netlist" method to write a new
    netlist file.

    :param netlist_file: Name of the .NET file to parse
    :type netlist_file: str or Path
    :param encoding: Forcing the encoding to be used on the circuit netlile read. Defaults to 'autodetect' which will
        call a function that tries to detect the encoding automatically. This however is not 100% foolproof.
    :type encoding: str, optional
    :param create_blank: Create a blank '.net' file when 'netlist_file' not exist. False by default
    :type create_blank: bool, optional
    """

    def __init__(self, netlist_file: Union[str, Path], encoding='autodetect', create_blank=False):
        super().__init__()
        self.netlist_file = Path(netlist_file)
        if create_blank:
            self.encoding = 'utf-8'  # when user want to create a blank netlist file, and didn't set encoding.
        else:
            if encoding == 'autodetect':
                try:
                    self.encoding = detect_encoding(self.netlist_file, r'^\*')  # Normally the file will start with a '*'
                except EncodingDetectError as err:
                    raise err
            else:
                self.encoding = encoding
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        # docstring inherited from BaseSchematic
        return self.netlist_file

    def add_instruction(self, instruction: str) -> None:
        """Adds a SPICE instruction to the netlist.

        For example:

        .. code-block:: text

                  .tran 10m ; makes a transient simulation
                  .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms ; Establishes a measuring
                  .step run 1 100, 1 ; makes the simulation run 100 times

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM
        if _is_unique_instruction(instruction):
            # Before adding new instruction, delete previously set unique instructions
            i = 0
            while i < len(self.netlist):
                line = self.netlist[i]
                if _is_unique_instruction(line):
                    self.netlist[i] = instruction
                    break
                else:
                    i += 1
        elif get_line_command(instruction) == '.PARAM':
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')

        # check whether the instruction is already there (dummy proofing)
        # TODO: if adding a .MODEL or .SUBCKT it should verify if it already exists and update it.
        if instruction not in self.netlist:
            # Insert before backanno instruction
            try:
                line = self.netlist.index(
                    '.backanno\n')  # TODO: Improve this. END of line termination could be differnt and case as well
            except ValueError:
                line = len(self.netlist) - 2  # This is where typically the .backanno instruction is
            self.netlist.insert(line, instruction)

    def remove_instruction(self, instruction) -> None:
        # docstring is in the parent class

        # TODO: Make it more intelligent so it recognizes .models, .param and .subckt
        # Because the netlist is stored containing the end of line terminations and because they are added when they
        # they are added to the netlist.
        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM
        if instruction in self.netlist:
            self.netlist.remove(instruction)
            _logger.info(f'Instruction "{instruction}" removed')
        else:
            _logger.error(f'Instruction "{instruction}" not found.')

    def remove_Xinstruction(self, search_pattern: str) -> None:
        # docstring is in the parent class
        regex = re.compile(search_pattern, re.IGNORECASE)
        i = 0
        instr_removed = False
        while i < len(self.netlist):
            line = self.netlist[i]
            if isinstance(line, str) and regex.match(line):
                del self.netlist[i]
                instr_removed = True
                _logger.info(f'Instruction "{line}" removed')
            else:
                i += 1
        if not instr_removed:
            _logger.error(f'No instruction matching pattern "{search_pattern}" was found')

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        # docstring is in the parent class
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)

        with open(run_netlist_file, 'w', encoding=self.encoding) as f:
            lines = iter(self.netlist)
            for line in lines:
                if isinstance(line, SpiceCircuit):
                    line._write_lines(f)
                else:
                    # Writes the modified sub-circuits at the end just before the .END clause
                    if line.upper().startswith(".END"):
                        # write here the modified sub-circuits
                        for sub in self.modified_subcircuits.values():
                            sub._write_lines(f)
                    f.write(line)

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Removes all previous edits done to the netlist, i.e. resets it to the original state.

        :returns: Nothing
        """
        super().reset_netlist(create_blank)
        self.modified_subcircuits.clear()
        if create_blank:
            lines = ['* netlist generated from spicelib', '.end']
            finished = self._add_lines(lines)
            if not finished:
                raise SyntaxError("Netlist with missing .END or .ENDS statements")
        elif self.netlist_file.exists():
            with open(self.netlist_file, 'r', encoding=self.encoding, errors='replace') as f:
                lines = iter(f)  # Creates an iterator object to consume the file
                finished = self._add_lines(lines)
                if not finished:
                    raise SyntaxError("Netlist with missing .END or .ENDS statements")
                # else:
                #     for _ in lines:  # Consuming the rest of the file.
                #         pass  # print("Ignoring %s" % _)
        else:
            _logger.error("Netlist file not found: {}".format(self.netlist_file))

    def run(self, wait_resource: bool = True,
            callback: Callable[[str, str], Any] = None, timeout: float = None, run_filename: str = None, simulator=None):
        """
        .. deprecated:: 1.0 Use the `run` method from the `SimRunner` class instead.

        Convenience function for maintaining legacy with legacy code. Runs the SPICE simulation.
        """
        from ..sim.sim_runner import SimRunner
        runner = SimRunner(simulator=simulator)
        return runner.run(self, wait_resource=wait_resource, callback=callback, timeout=timeout, run_filename=run_filename)
