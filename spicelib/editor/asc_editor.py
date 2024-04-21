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
# Name:        asc_editor.py
# Purpose:     Class made to update directly the LTspice ASC files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import os.path
from pathlib import Path
from typing import Union, Optional
import re
import logging
from ..utils.file_search import find_file_in_directory
from .base_editor import BaseEditor, format_eng, ComponentNotFoundError, ParameterNotFoundError, PARAM_REGEX, \
    UNIQUE_SIMULATION_DOT_INSTRUCTIONS, Component
from .base_schematic import (BaseSchematic, Point, Line, Text, SchematicComponent, ERotation, HorAlign, VerAlign,
                             TextTypeEnum, Port)

_logger = logging.getLogger("spicelib.AscEditor")

TEXT_REGEX = re.compile(r"TEXT (-?\d+)\s+(-?\d+)\s+(Left|Right|Top|Bottom)\s(\d+)\s*(?P<type>[!;])(?P<text>.*)",
                        re.IGNORECASE)
TEXT_REGEX_X = 1
TEXT_REGEX_Y = 2
TEXT_REGEX_ALIGN = 3
TEXT_REGEX_SIZE = 4
TEXT_REGEX_TYPE = 5
TEXT_REGEX_TEXT = 6

END_LINE_TERM = "\n"


ASC_ROTATION_DICT = {
    'R0': ERotation.R0,
    'R90': ERotation.R90,
    'R180': ERotation.R180,
    'R270': ERotation.R270,
    'M0': ERotation.M0,
    'M90': ERotation.M90,
    'M180': ERotation.M180,
    'M270': ERotation.M270,
}

ASC_INV_ROTATION_DICT = {val: key for key, val in ASC_ROTATION_DICT.items()}

LT_ATTRIBUTE_NUMBERS = {
    'Prefix': 0,
    'Type': 1,
    'Value': 3,
    'Value2': 123,
    'SpiceModel': 38,
    'ModelFile': 'X',
    'Def_Sub': 'X',
    'SpiceLine': 39,
    'SpiceLine2': 40,
}

LT_ATTRIBUTE_NUMBERS_INV = {val: key for key, val in LT_ATTRIBUTE_NUMBERS.items()}

WEIGHT_CONVERSION_TABLE = ('Thin', 'Normal', 'Thick')


def asc_text_align_set(text: Text, alignment: str):
    if alignment == 'Left':
        text.textAlignment = HorAlign.LEFT
        text.verticalAlignment = VerAlign.CENTER
    elif alignment == 'Center':
        text.textAlignment = HorAlign.CENTER
        text.verticalAlignment = VerAlign.CENTER
    elif alignment == 'Right':
        text.textAlignment = HorAlign.RIGHT
        text.verticalAlignment = VerAlign.CENTER
    elif alignment == 'VTop':
        text.textAlignment = HorAlign.CENTER
        text.verticalAlignment = VerAlign.TOP
    elif alignment == 'VCenter':
        text.textAlignment = HorAlign.CENTER
        text.verticalAlignment = VerAlign.CENTER
    elif alignment == 'VBottom':
        text.textAlignment = HorAlign.LEFT
        text.verticalAlignment = VerAlign.BOTTOM
    else:
        # Default
        text.textAlignment = HorAlign.LEFT
        text.verticalAlignment = VerAlign.CENTER
    return text


def asc_text_align_get(text: Text) -> str:
    if text.verticalAlignment == VerAlign.CENTER:
        if text.textAlignment == HorAlign.RIGHT:
            return 'Right'
        elif text.textAlignment == HorAlign.CENTER:
            return 'Center'
        else:
            return 'Left'
    else:
        if text.verticalAlignment == VerAlign.TOP:
            return 'VTop'
        elif text.verticalAlignment == VerAlign.CENTER:
            return 'VCenter'
        elif text.verticalAlignment == VerAlign.BOTTOM:
            return 'VBottom'
        else:
            return 'Left'


class AscEditor(BaseSchematic):
    """Class made to update directly the LTspice ASC files"""
    lib_paths = []  # This is a class variable, so it can be shared between all instances.

    def __init__(self, asc_file: str):
        super().__init__()
        self.version = 4
        self.sheet = "1 0 0"  # Three values are present on the SHEET clause
        self.asc_file_path = Path(asc_file)
        if not self.asc_file_path.exists():
            raise FileNotFoundError(f"File {asc_file} not found")
        # read the file into memory
        self.reset_netlist()

    @property
    def circuit_file(self) -> Path:
        return self.asc_file_path

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        run_netlist_file = run_netlist_file.with_suffix(".asc")
        with open(run_netlist_file, 'w') as asc:
            _logger.info(f"Writing ASC file {run_netlist_file}")

            asc.write(f"Version {self.version}" + END_LINE_TERM)
            asc.write(f"SHEET {self.sheet}" + END_LINE_TERM)
            for wire in self.wires:
                asc.write(f"WIRE {wire.V1.X} {wire.V1.Y} {wire.V2.X} {wire.V2.Y}" + END_LINE_TERM)
            for flag in self.labels:
                asc.write(f"FLAG {flag.coord.X} {flag.coord.Y} {flag.text}" + END_LINE_TERM)
            for component in self.components.values():
                symbol = component.symbol
                posX = component.position.X
                posY = component.position.Y
                rotation = ASC_INV_ROTATION_DICT[component.rotation]
                asc.write(f"SYMBOL {symbol} {posX} {posY} {rotation}" + END_LINE_TERM)
                for attr, value in component.attributes.items():
                    if attr.startswith('_WINDOW') and isinstance(value, Text):
                        num_ref = attr[len("_WINDOW_"):]
                        posX = value.coord.X
                        posY = value.coord.Y
                        alignment = asc_text_align_get(value)
                        size = value.size
                        asc.write(f"WINDOW {num_ref} {posX} {posY} {alignment} {size}" + END_LINE_TERM)
                asc.write(f"SYMATTR InstName {component.reference}" + END_LINE_TERM)
                if component.reference.startswith('X') and "_SUBCKT" in component.attributes:
                    # writing the sub-circuit if it was updated
                    sub_circuit: AscEditor = component.attributes["_SUBCKT"]
                    if sub_circuit.updated:
                        sub_circuit.save_netlist(sub_circuit.asc_file_path)
                for attr, value in component.attributes.items():
                    if not attr.startswith('_'):  # All these are not exported since they are only used internally
                        asc.write(f"SYMATTR {attr} {value}" + END_LINE_TERM)
            for directive in self.directives:
                posX = directive.coord.X
                posY = directive.coord.Y
                alignment = asc_text_align_get(directive)
                size = directive.size
                if directive.type == TextTypeEnum.DIRECTIVE:
                    directive_type = '!'
                else:
                    directive_type = ';'  # Otherwise assume it is a comment
                asc.write(f"TEXT {posX} {posY} {alignment} {size} {directive_type}{directive.text}" + END_LINE_TERM)

    def reset_netlist(self, create_blank: bool = False) -> None:
        super().reset_netlist()
        with open(self.asc_file_path, 'r') as asc_file:
            _logger.info(f"Parsing ASC file {self.asc_file_path}")
            component = None
            for line in asc_file:
                if line.startswith("SYMBOL"):
                    tag, symbol, posX, posY, rotation = line.split()
                    if component is not None:
                        assert component.reference is not None, "Component InstName was not given"
                        self.components[component.reference] = component
                    component = SchematicComponent()
                    component.symbol = symbol
                    component.position.X = int(posX)
                    component.position.Y = int(posY)
                    if rotation in ASC_ROTATION_DICT:
                        component.rotation = ASC_ROTATION_DICT[rotation]
                    else:
                        raise ValueError(f"Invalid Rotation value: {rotation}")
                elif line.startswith("WINDOW"):
                    assert component is not None, "Syntax Error: WINDOW clause without SYMBOL"
                    tag, num_ref, posX, posY, alignment, size = line.split()
                    coord = Point(int(posX), int(posY))
                    text = Text(coord=coord, text=num_ref, size=size, type=TextTypeEnum.ATTRIBUTE)
                    text = asc_text_align_set(text, alignment)
                    component.attributes['_WINDOW ' + num_ref] = text

                elif line.startswith("SYMATTR"):
                    assert component is not None, "Syntax Error: SYMATTR clause without SYMBOL"
                    tag, ref, text = line.split(maxsplit=2)
                    text = text.strip()  # Gets rid of the \n terminator
                    if ref == "InstName":
                        component.reference = text
                        if component.reference.startswith('X'):  # This is a subcircuit
                            # then create the attribute "SUBCKT"
                            component.attributes["_SUBCKT"] = self._get_symbol_circuit(component.symbol)
                    else:
                        component.attributes[ref] = text
                elif line.startswith("TEXT"):
                    match = TEXT_REGEX.match(line)
                    if match:
                        text = match.group(TEXT_REGEX_TEXT)
                        X = int(match.group(TEXT_REGEX_X))
                        Y = int(match.group(TEXT_REGEX_Y))
                        coord = Point(X, Y)
                        size = int(match.group(TEXT_REGEX_SIZE))
                        if match.group(TEXT_REGEX_TYPE) == "!":
                            ttype = TextTypeEnum.DIRECTIVE
                        else:
                            ttype = TextTypeEnum.COMMENT
                        alignment = match.group(TEXT_REGEX_ALIGN)
                        text = Text(coord=coord, text=text.strip(), size=size, type=ttype)
                        text = asc_text_align_set(text, alignment)
                        self.directives.append(text)

                elif line.startswith("WIRE"):
                    tag, x1, y1, x2, y2 = line.split()
                    v1 = Point(int(x1), int(y1))
                    v2 = Point(int(x2), int(y2))
                    wire = Line(v1, v2)
                    self.wires.append(wire)
                elif line.startswith("FLAG"):
                    tag, posX, posY, text = line.split(maxsplit=4)
                    coord = Point(int(posX), int(posY))
                    flag = Text(coord=coord, text=text, type=TextTypeEnum.LABEL)
                    self.labels.append(flag)
                elif line.startswith("Version"):
                    tag, version = line.split()
                    assert version in ["4"], f"Unsupported version : {version}"
                    self.version = version
                elif line.startswith("SHEET "):
                    self.sheet = line[len("SHEET "):].strip()
                elif line.startswith("IOPIN "):
                    tag, posX, posY, direction = line.split()
                    text = self.labels[-1]  # Assuming it is the last FLAG parsed
                    assert text.coord.X == int(posX) and text.coord.Y == int(posY), "Syntax Error, getting a IOPIN withou an associated label"
                    port = Port(text, direction)
                    self.ports.append(port)
                else:
                    raise NotImplementedError("Primitive not supported for ASC file\n" 
                                              f'"{line}"')
            if component is not None:
                assert component.reference is not None, "Component InstName was not given"
                self.components[component.reference] = component

    def _get_symbol_circuit(self, symbol: str):
        asc_filename = symbol + os.path.extsep + "asc"
        asc_path = self._lib_file_find(asc_filename)
        answer = AscEditor(asc_path)
        return answer

    def get_subcircuit(self, reference: str) -> 'AscEditor':
        """Returns an AscEditor file corresponding to the symbol"""
        sub = self.get_component(reference)
        return sub.attributes["_SUBCKT"]

    def get_component_info(self, reference) -> dict:
        """Returns the reference information as a dictionary"""
        component = self.get_component(reference)
        info = {name: value for name, value in component.attributes.items() if not name.startswith("WINDOW ")}
        info["InstName"] = reference  # For legacy purposes
        return info

    def get_component_position(self, reference: str) -> (Point, ERotation):
        component = self.get_component(reference)
        return component.position, component.rotation

    def set_component_position(self, reference: str, position: Point, rotation: ERotation) -> None:
        component = self.get_component(reference)
        component.position = position
        component.rotation = rotation

    def _get_directive(self, command, search_expression: re.Pattern):
        command_upped = command.upper()
        for directive in self.directives:
            command_upped_directive = directive.text.upper()
            if command_upped_directive.startswith(command_upped):
                match = search_expression.search(directive.text)
                if match:
                    return match, directive
        return None, None

    def get_parameter(self, param: str) -> str:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        match, directive = self._get_directive(".PARAM", param_regex)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in ASC file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        match, directive = self._get_directive(".PARAM", param_regex)
        if match:
            _logger.debug(f"Parameter {param} found in ASC file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            start, stop = match.span('replace')
            directive.text = f"{directive.text[:start]}{param}={value_str}{directive.text[stop:]}"
            _logger.info(f"Parameter {param} updated to {value_str}")
        else:
            # Was not found so we need to add it,
            _logger.debug(f"Parameter {param} not found in ASC file, adding it")
            x, y = self._get_text_space()
            coord = Point(x, y)
            text = f".param {param}={value}"
            directive = Text(coord=coord, text=text, size=2, type=TextTypeEnum.DIRECTIVE)
            _logger.info(f"Parameter {param} added with value {value}")
            self.directives.append(directive)
        self.updated = True

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        component = self.get_component(device)
        if "Value" in component.attributes:
            if isinstance(value, str):
                value_str = value
            else:
                value_str = format_eng(value)
            component.attributes["Value"] = value_str
            _logger.info(f"Component {device} updated to {value_str}")
            self.set_updated(device)
        else:
            _logger.error(f"Component {device} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {device} does not have a Value attribute")

    def set_element_model(self, element: str, model: str) -> None:
        component = self.get_component(element)
        component.symbol = model
        _logger.info(f"Component {element} updated to {model}")
        self.set_updated(element)

    def get_component_value(self, element: str) -> str:
        component = self.get_component(element)
        if "Value" not in component.attributes:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return component.attributes["Value"]

    def get_components(self, prefixes='*') -> list:
        if prefixes == '*':
            return list(self.components.keys())
        return [k for k in self.components.keys() if k[0] in prefixes]

    def remove_component(self, designator: str):
        sub_circuit, ref = self._get_parent(designator)
        del sub_circuit.components[ref]
        sub_circuit.updated = True

    def _get_text_space(self):
        """
        Returns the coordinate on the Schematic File canvas where a text can be appended.
        """
        min_x = 100000  # High enough to be sure it will be replaced
        max_x = -100000
        min_y = 100000  # High enough to be sure it will be replaced
        max_y = -100000
        _, x, y = self.sheet.split()
        min_x = min(min_x, int(x))
        min_y = min(min_y, int(y))
        for wire in self.wires:
            min_x = min(min_x, wire.V1.X, wire.V2.X)
            max_x = max(max_x, wire.V1.X, wire.V2.X)
            min_y = min(min_y, wire.V1.Y, wire.V2.Y)
            max_y = max(max_y, wire.V1.Y, wire.V2.Y)
        for flag in self.labels:
            min_x = min(min_x, flag.coord.X)
            max_x = max(max_x, flag.coord.X)
            min_y = min(min_y, flag.coord.Y)
            max_y = max(max_y, flag.coord.Y)
        for directive in self.directives:
            min_x = min(min_x, directive.coord.X)
            max_x = max(max_x, directive.coord.X)
            min_y = min(min_y, directive.coord.Y)
            max_y = max(max_y, directive.coord.Y)
        for component in self.components.values():
            min_x = min(min_x, component.position.X)
            max_x = max(max_x, component.position.X)
            min_y = min(min_y, component.position.Y)
            max_y = max(max_y, component.position.Y)

        return min_x, max_y + 24  # Setting the text in the bottom left corner of the canvas

    def add_library_paths(self, *paths):
        """Adding paths for searching for symbols and libraries"""
        self.lib_paths.extend(*paths)

    def _lib_file_find(self, filename) -> Optional[str]:
        for sym_root in self.lib_paths + [
            # os.path.curdir,  # The current script directory
            os.path.split(self.asc_file_path)[0],  # The directory where the script is located
            os.path.expanduser(r"~\AppData\Local\LTspice\lib\sym"),
            os.path.expanduser(r"~\Documents\LtspiceXVII\lib\sym"),
            # os.path.expanduser(r"~\AppData\Local\Programs\ADI\LTspice\lib.zip"), # TODO: implement this
        ]:
            print(f"   {os.path.abspath(sym_root)}")
            if not os.path.exists(sym_root):  # Skipping invalid paths
                continue
            if sym_root.endswith('.zip'):
                pass
                # TODO: Using an IO buffer to pass the file to the AsyEditor
            else:
                file_found = find_file_in_directory(sym_root, filename)
                if file_found is not None:
                    return file_found
        return None

    def add_instruction(self, instruction: str) -> None:
        instruction = instruction.strip()  # Clean any end of line terminators
        set_command = instruction.split()[0].upper()

        if set_command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            i = 0
            while i < len(self.directives):
                directive = self.directives[i]
                if directive.type == TextTypeEnum.COMMENT:
                    continue  # this is a comment
                directive_command = directive.text.split()[0].upper()
                if directive_command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
                    directive.text = instruction
                    self.updated = True
                    return  # Job done, can exit this method
                i += 1
        elif set_command.startswith('.PARAM'):
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')
        # If we get here, then the instruction was not found, so we need to add it
        x, y = self._get_text_space()
        coord = Point(x, y)
        directive = Text(coord=coord, text=instruction, size=2, type=TextTypeEnum.DIRECTIVE)
        self.directives.append(directive)
        self.updated = True

    def remove_instruction(self, instruction: str) -> None:
        i = 0
        while i < len(self.directives):
            if instruction in self.directives[i].text:
                text = self.directives[i].text
                del self.directives[i]
                _logger.info(f"Instruction {text} removed")
                self.updated = True
                return  # Job done, can exit this method
            i += 1

        msg = f'Instruction "{instruction}" not found'
        _logger.error(msg)
        raise RuntimeError(msg)

    def remove_Xinstruction(self, search_pattern: str) -> None:
        regex = re.compile(search_pattern, re.IGNORECASE)
        instr_removed = False
        i = 0
        while i < len(self.directives):
            instruction = self.directives[i].text
            if regex.match(instruction) is not None:
                instr_removed = True
                del self.directives[i]
                _logger.info(f"Instruction {instruction} removed")
            else:
                i += 1
        if instr_removed:
            self.updated = True
        else:
            msg = f'Instructions matching "{search_pattern}" not found'
            _logger.error(msg)
