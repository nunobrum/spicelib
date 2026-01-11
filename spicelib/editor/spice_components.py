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
# Name:        spice_components.py
# Purpose:     Parse and manipulate SPICE components in a netlist
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from collections import OrderedDict
from typing import Dict
import re
import io
import logging

from .editor_errors import UnrecognizedSyntaxError
from .primitives import Component, format_eng, to_float
from .updates import UpdateType
from .spice_utils import END_LINE_TERM, REPLACE_REGEXS
from ..log.logfile_data import try_convert_value

_logger = logging.getLogger("spicelib.SpiceEditor")



# Code Optimization objects, avoiding repeated compilation of regular expressions
component_replace_regexs: Dict[str, re.Pattern] = {}
for prefix, pattern in REPLACE_REGEXS.items():
    # print(f"Compiling regex for {prefix}: {pattern}")
    component_replace_regexs[prefix] = re.compile(pattern, re.IGNORECASE)


def _clean_line(line: str) -> str:
    """remove extra spaces and clean up the line so that the regexes have an easier time matching

    :param line: spice netlist string
    :type line: str
    :return: spice netlist string cleaned up
    :rtype: str
    """
    if line is None:
        return ""
    # Remove any leading or trailing spaces
    line = line.strip()
    # condense all space sequences to a single space
    line = re.sub(r'\s+', ' ', line).strip()
    # Remove any spaces before or after the '=' sign
    line = line.replace(" =", "=")
    line = line.replace("= ", "=")
    # Remove any spaces before or after the ',' sign (for constructions like "key=val1, val2")
    line = line.replace(" ,", ",")
    line = line.replace(", ", ",")
    return line


def _parse_params(params_str: str) -> dict:
    """
    Parses the parameters string and returns a dictionary with the parameters.
    The parameters are in the form of key=value, separated by spaces.
    The values may contain spaces or sequences with comma separation

    :param params_str: input
    :type params_str: str
    :raises ValueError: invalid format
    :return: dict with parameters
    :rtype: dict
    """
    params = OrderedDict()
    # make sure all spaces are condensed and there are no spaces around the = sign
    params_str = _clean_line(params_str)
    if len(params_str) == 0:
        return params

    # now split in pairs
    # This will match key=value pairs, where value may contain spaces, but not unescaped '=' signs

    # TODO in case of a qspice verilog component (Ø), allow "type key=value", but that is not easy to do, as we do not know the component type here
    # Here are the allowed types, just in case this will be correctly implemented one day:
    # verilog_types = [
    #     "bit",
    #     "bool",
    #     "boolean",
    #     "int8_t",
    #     "int8",
    #     "char",
    #     "char",
    #     "uint8_t",
    #     "uint8",
    #     "uchar",
    #     "uchar",
    #     "byte",
    #     "int16_t",
    #     "int16",
    #     "uint16_t",
    #     "uint16",
    #     "int32_t",
    #     "int32",
    #     "int",
    #     "uint32_t",
    #     "uint32",
    #     "uint",
    #     "int64_t",
    #     "int64",
    #     "uint64_t",
    #     "uint64",
    #     "shortfloat",
    #     "float",
    #     "double",
    # ]
    pattern = r"(\w+)=(.*?)(?<!\\)(?=\s+\w+=|$)"
    matches = re.findall(pattern, params_str)
    if matches:
        for key, value in matches:
            params[key] = try_convert_value(value)
        return params
    else:
        raise ValueError(f"Invalid parameter format: '{params_str}'")

def _insert_section(line: str, start: int, end: int, section: str) -> str:
    """
    Inserts a section in the line at the given start and end positions.
    Makes sure the section is surrounded by spaces and the line ends with a newline
    """
    if not line:
        return ""
    if not section:  # Nothing to insert
        return line

    section = section.strip()
    # TODO why do we need a space? In the construction 'a=1' that must become 'a=2' a space should not be needed.
    if start > 0 and line[start - 1] != ' ':
        section = ' ' + section
    if end < len(line) and line[end] != ' ' and len(section) > 1:
        section = section + ' '
    line = line[:start] + section + line[end:]
    line = line.strip()
    return line

class SpiceComponent(Component):
    """
    Represents a SPICE component in the netlist. It allows the manipulation of the parameters and the value of the
    component.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the SpiceComponent"""
        super().__init__(*args, **kwargs)

    # def absolute_reference(self) -> str:
    #     """Get the absolute reference of the component inside the netlist
    #
    #     :return: absolute reference
    #     :rtype: str
    #     """
    #     if self._netlist is not None:
    #         return self._netlist.parent_reference() + self.reference
    #     return self.reference

    def reset_attributes(self):
        """Update attributes of a component at a specific line in the netlist

        :raises NotImplementedError: When the component type is not recognized
        :raises UnrecognizedSyntaxError: When the line doesn't match the expected REGEX.
        :return: The match found
        :rtype: re.match

        :meta private:
        """
        prefix = self._obj[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {self._obj}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        new_line = re.sub(r'[\n\r]+\s*', ' ', self._obj) # cleans up line breaks and extra spaces and tabs
        match = regex.match(new_line)
        if match is None:
            raise UnrecognizedSyntaxError(self._obj, regex.pattern)

        info = match.groupdict()
        self.attributes.clear()
        for attr in info:
            if attr == 'designator':
                ref = info[attr]
                if len(ref) > 2 and ref[1] == '§':
                    # strip any §, it is not always present and seems optional, so scrap it
                    ref = ref[0] + ref[2:]
                self.reference = ref
            elif attr == 'nodes':
                self.ports = info[attr].split()
            elif attr == 'params':
                if info[attr]:
                    self.set_parameters(**_parse_params(info[attr]))
            elif attr in ('number', 'formula1', 'formula2', 'formula3'):
                continue  # these are subgroups of VALUE, ignore
            else:
                if info[attr] is not None:  # Only sets attributes that are present
                    setattr(self, attr, info[attr])
        return match

    def rewrite_lines(self, stream: io.StringIO) -> int:
        """Write the SPICE representation of the component into a stream

        :return: Number of characters written
        :rtype: int
        """
        # Reconstruct the line from the attributes. This will not preserve the original formatting, by reparsing
        # again the line updating the parameters.
        prefix = self.reference[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {self._obj}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        match = regex.match(self._obj)
        if match is None:
            raise UnrecognizedSyntaxError(self._obj, regex.pattern)
        info = match.groupdict()
        new_line = self._obj[:]  # make a copy
        new_line = re.sub(r'[\n\r]+\s*', ' ', new_line)
        offset = 0
        update_done = False
        for attr in info:
            start, stop = match.span(attr)
            if attr == 'designator':
                old_ref = info[attr]
                if len(old_ref) > 2 and old_ref[1] == '§':
                    # strip any §, it is not always present and seems optional, so scrap it
                    old_ref = old_ref[0] + old_ref[2:]
                    add_odd_char = True
                else:
                    add_odd_char = False
                if self.reference != old_ref:
                    if add_odd_char:
                        new_ref = self.reference[0] + '§' + self.reference[1:]
                    else:
                        new_ref = self.reference
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_ref)
                    offset += len(new_ref) - len(old_ref)
                    update_done = True
            elif attr == 'nodes':
                old_nodes_str = info[attr]
                new_nodes_str = ' '+ ' '.join(self.ports)
                if old_nodes_str != new_nodes_str:
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_nodes_str)
                    offset += len(new_nodes_str) - len(old_nodes_str)
                    update_done = True
            elif attr == 'params':
                old_params_str = info[attr] or ""  # in case of no params, make it empty string
                new_params_dict = self.params
                new_params_str = ' '.join(f"{key}={value}" for key, value in new_params_dict.items())
                if old_params_str != new_params_str:
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_params_str)
                    offset += len(new_params_str) - len(old_params_str)
                    update_done = True
            else:
                if hasattr(self, attr):
                    old_attr_value = info[attr]
                    if attr == 'value':
                        attr = 'value_str'
                    new_attr_value = self[attr]
                    if old_attr_value != new_attr_value:
                        new_line = _insert_section(new_line, start + offset, stop + offset, new_attr_value)
                        offset += len(new_attr_value) - len(old_attr_value)
                        update_done = True
                else:
                    pass  # attribute not present, do nothing
        if not update_done:
            # nothing changed, write original line
            new_line = self._obj
        else:
            new_line += END_LINE_TERM
        stream.write(new_line)
        return len(new_line)

    def write_lines(self, stream: io.StringIO) -> int:
        """Get the SPICE representation of the component as a string. This creates a new line from the attributes alone

        :return: number of characters written
        :rtype: int
        """
        if self._obj != "":
            # try to rewrite the line preserving formatting
            return self.rewrite_lines(stream)

        # Write a line from the stored attributes
        count = stream.write(self.reference)
        for port in self.ports:
            count += stream.write(f" {port}")
        # Write value if present
        if 'value' in self.attributes:
            count += stream.write(f" {self.value_str}")
        if 'model' in self.attributes:
            count += stream.write(f" {self.model}")
        # Write parameters
        line_size = count
        for key, value in self.params.items():
            if line_size == 0:
                count += stream.write("+") # continuation line
                line_size = 1
            chars = stream.write(f" {key}={value}")
            count += chars
            line_size += chars
            if line_size > 80:
                stream.write("\n")  # continuation line
                line_size = 0  # account for the space at the beginning of the new line

        stream.write(END_LINE_TERM)
        count += len(END_LINE_TERM)
        return count

    def set_value(self, value):
        """Informs the netlist that the value of the component has changed"""
        super().set_value(value)
        self.netlist.add_update(self.reference, value, UpdateType.UpdateComponentValue)

    def set_parameters(self, **params):
        """Informs the netlist that the parameters of the component have changed"""
        super().set_parameters(**params)
        self.netlist.add_update(self.reference,  str(params), UpdateType.UpdateComponentParameter)

    def set_parameter(self, key: str, value):
        """Informs the netlist that a parameter of the component has changed"""
        super().set_parameter(key, value)
        self.netlist.add_update(self.reference, f"{key}={value}", UpdateType.UpdateComponentParameter)




