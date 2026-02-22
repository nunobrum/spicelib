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
from .primitives import Component
from .updates import UpdateType
from .spice_utils import END_LINE_TERM, REPLACE_REGEXS

_logger = logging.getLogger("spicelib.SpiceEditor")

VERILOG_TYPES = (
    "bit",
    "bool",
    "boolean",
    "int8_t",
    "int8",
    "char",
    "char",
    "uint8_t",
    "uint8",
    "uchar",
    "uchar",
    "byte",
    "int16_t",
    "int16",
    "uint16_t",
    "uint16",
    "int32_t",
    "int32",
    "int",
    "uint32_t",
    "uint32",
    "uint",
    "int64_t",
    "int64",
    "uint64_t",
    "uint64",
    "shortfloat",
    "float",
    "double",
)

SPICE_KEYWORDS = (
    "noiseless",
)


# Code Optimization objects, avoiding repeated compilation of regular expressions
component_replace_regexs: Dict[str, re.Pattern] = {}
for prefix, pattern in REPLACE_REGEXS.items():
    # print(f"Compiling regex for {prefix}: {pattern}")
    component_replace_regexs[prefix] = re.compile(pattern, re.IGNORECASE)


#TODO: complete the parser and integrate it in the Spice Editor parser.
# When writing back to the netlist they should be written in the same format. Also make sure to handle line
# continuations and comments correctly when parsing and writing back to the netlist.

def try_value(token: str):
    """Try to convert a token to an int or float, if it fails return the original string"""
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token
    return token


def tokenize_params(params_str: str) -> list[str]:
    """Split by spaces and special operators (= and ,) but keep the operators as part of the tokens
    Everything insider {} or "" or '' will be considered as part of the same token, so that parameters like
    "key={value with spaces and commas}" are correctly parsed as a single token."""
    in_quotes = None  # To keep track of which quote we are in, if any
    in_func_decl = False  # Inside {}
    tokens = []
    current_token = ""

    for char in params_str:
        # Use structural pattern matching for clearer branching and guards
        match char:
            case '"' | "'":
                if in_quotes is None:
                    in_quotes = char
                elif in_quotes == char:
                    in_quotes = None
                current_token += char
            case '{':
                in_func_decl = True
                current_token += char
            case '}':
                in_func_decl = False
                current_token += char
            case c if c in (',', '=') and in_quotes is None and not in_func_decl:
                if current_token:
                    tokens.append(current_token.strip())
                    tokens.append(c)
                    current_token = ""
            case c if c.isspace() and in_quotes is None and not in_func_decl:
                if current_token:
                    tokens.append(current_token.strip())
                    current_token = ""
            case _:
                current_token += char

    if current_token:
        tokens.append(current_token.strip())
    return tokens


def undress_designator(designator: str) -> str:
    """Removes any odd characters from the designator, such as §, which is sometimes used in the netlist but not always present. This is needed to compare the designator with the reference of the component, which does not contain these odd characters."""
    if len(designator) > 2 and designator[1] == '§':
        return designator[0] + designator[2:]
    return designator

def _parse_params(params_str: str) -> dict:
    """
    Parses the parameters string and returns a dictionary with the parameters.
    The parameters, which can be in the form of "key=value", but the value
    can contain spaces and commas, such as "key=value1, value2". Also handle type qualifiers such
    as "type key=value" where the types are the verilog defined types as defined in VERILOG_TYPES.

    :param params_str: input
    :type params_str: str
    :raises ValueError: invalid format
    :return: dict with parameters
    :rtype: dict
    """
    params = OrderedDict()

    # Now we have a list of tokens, we can parse them into key-value pairs
    tokens = tokenize_params(params_str)
    if not tokens:
        return params  # empty parameters because there were no tokens

    key = None # current key being parsed, we expect the next token to be its value
    last_key = None  # last key parsed, we expect the next token to be a comma if we are parsing a list of values for the same key
    # var_type = None # if the current token is a type qualifier, we store it here and apply it to the next key we find
    is_list = False  #

    for token in tokens:
        if token == '=':
            if key is None:
                raise ValueError(f"Unexpected '=' without a key before it in parameters string: {params_str}")
            continue
        elif token == ',':
            if last_key and last_key in params:
                is_list = True
            else:
                raise ValueError(f"Unexpected ',' without a value after it in parameters string: {params_str}")
        else:
            value = try_value(token)
            if is_list:
                if last_key is None:
                    raise ValueError(f"Unexpected value '{token}' without a key in parameters string: {params_str}")
                # already assured that the
                if isinstance(params[last_key], list):
                    params[last_key].append(value)
                else:
                    params[last_key] = [params[last_key], value]
                is_list = False
            elif key is None:
                if token in SPICE_KEYWORDS:
                    # if the token is a keyword, we consider it as a key with value True
                    params[token] = True
                elif token in VERILOG_TYPES:
                    # if the token is a verilog type, we consider it as a type qualifier for the next key
                    var_type = token
                elif isinstance(value, float | int) and last_key in params:
                    # if the token can be converted to a value, we consider it as a list of values for the last key
                    if isinstance(params[last_key], str):
                        params[last_key] += f" {token}"
                    else:
                        params[last_key] = f"{params[last_key]} {token}"
                else:
                    key = token
            else:
                # if var_type:
                #    # if there is a type qualifier, we prepend it to the key
                #    params[key] = (value, var_type)
                #    var_type = None
                # else:
                params[key] = value
                last_key = key
                key = None

    return params

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
                self.reference = undress_designator(info[attr])
            elif attr == 'nodes':
                self.ports = info[attr].split()
            elif attr == 'value':
                if info[attr] is not None:
                    self.set_value(info[attr].strip())
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
            if start == -1 and stop == -1 and attr not in self.attributes:
                continue  # this attribute is not present in the line, skip it
            if attr == 'designator':
                old_ref = undress_designator(info[attr])
                if self.reference != old_ref:
                    if '§' in info[attr]:
                        new_ref = self.reference[0] + '§' + self.reference[1:]
                    else:
                        new_ref = self.reference
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_ref)
                    offset += len(new_ref) - len(old_ref)
                    update_done = True
            elif attr == 'nodes':
                old_nodes_str = info[attr]
                new_nodes_str = ' ' + ' '.join(self.ports)
                if old_nodes_str != new_nodes_str:
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_nodes_str)
                    offset += len(new_nodes_str) - len(old_nodes_str)
                    update_done = True
            elif attr == 'params':
                old_params_str = info[attr] or ""  # in case of no params, make it empty string
                old_params = _parse_params(old_params_str)
                # Now compare the old params with the new params, if they are different, we need to update the line
                differences = False
                for key in self.params:
                    if key not in old_params:
                        differences = True
                        break
                    if self.params[key] != old_params[key]:
                        differences = True
                        break
                else:
                    for key in old_params:
                        if key not in self.params:
                            differences = True
                            break
                if differences:
                    new_params = []
                    for key, value in self.params.items():
                        if isinstance(value, list):
                            value_str = ','.join(str(v) for v in value)
                        else:
                            value_str = str(value)
                        new_params.append(f"{key}={value_str}")
                    new_params_str = ' '.join(new_params)
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
