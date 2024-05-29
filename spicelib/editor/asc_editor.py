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
from ..utils.detect_encoding import detect_encoding, EncodingDetectError
import re
import logging

from .ltspice_utils import TEXT_REGEX, TEXT_REGEX_X, TEXT_REGEX_Y, TEXT_REGEX_ALIGN, TEXT_REGEX_SIZE, TEXT_REGEX_TYPE, \
    TEXT_REGEX_TEXT, END_LINE_TERM, ASC_ROTATION_DICT, ASC_INV_ROTATION_DICT, asc_text_align_set, asc_text_align_get
from .spice_editor import SpiceEditor, SpiceCircuit
from ..utils.file_search import search_file_in_containers
from .base_editor import format_eng, ComponentNotFoundError, ParameterNotFoundError, PARAM_REGEX, \
    UNIQUE_SIMULATION_DOT_INSTRUCTIONS
from .base_schematic import (BaseSchematic, Point, Line, Text, SchematicComponent, ERotation, TextTypeEnum, Port)
from .asy_reader import AsyReader

from ..log.logfile_data import try_convert_value

_logger = logging.getLogger("spicelib.AscEditor")


LTSPICE_PARAMETERS = ("Value", "Value2", "SpiceModel", "SpiceLine", "SpiceLine2")
LTSPICE_PARAMETERS_REDUCED = ("SpiceLine", "SpiceLine2")
LTSPICE_ATTRIBUTES = ("InstName", "Def_Sub")


class AscEditor(BaseSchematic):
    """Class made to update directly the LTspice ASC files"""
    lib_paths = []  # This is a class variable, so it can be shared between all instances.
    symbol_cache = {}  # This is a class variable, so it can be shared between all instances.

    def __init__(self, asc_file: Union[str, Path], encoding='autodetect'):
        super().__init__()
        self.version = 4
        self.sheet = "1 0 0"  # Three values are present on the SHEET clause
        self.asc_file_path = Path(asc_file)
        if not self.asc_file_path.exists():
            raise FileNotFoundError(f"File {asc_file} not found")
        # determine encoding
        if encoding == 'autodetect':
            try:
                self.encoding = detect_encoding(self.asc_file_path, r'^VERSION ', re_flags=re.IGNORECASE)  # Normally the file will start with 'VERSION '
            except EncodingDetectError as err:
                raise err
        else:
            self.encoding = encoding        
        # read the file into memory
        self.reset_netlist()

    @property
    def circuit_file(self) -> Path:
        return self.asc_file_path

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        run_netlist_file = run_netlist_file.with_suffix(".asc")
        with open(run_netlist_file, 'w', encoding=self.encoding) as asc:
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
        with open(self.asc_file_path, 'r', encoding=self.encoding) as asc_file:
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
                        symbol = self._get_symbol(component.symbol)
                        if component.reference.startswith('X') or symbol.is_subcircuit():  # This is a subcircuit
                            # then create the attribute "SUBCKT"
                            component.attributes["_SUBCKT"] = self._get_subcircuit(symbol)
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

    def _get_symbol(self, symbol: str) -> AsyReader:
        asy_filename = symbol + os.path.extsep + "asy"
        asy_path = self._asy_file_find(asy_filename)
        if asy_path is None:
            raise FileNotFoundError(f"File {asy_filename} not found")
        answer = AsyReader(asy_path)
        return answer

    def _get_subcircuit(self, symbol: AsyReader) -> Union[SpiceEditor, 'AscEditor']:
        # if it is a an ASC file, then we need to read it
        if symbol.symbol_type == "BLOCK":
            asc_filename = symbol.get_schematic_file()
            if asc_filename.exists():
                asc_path = asc_filename
            else:
                asc_path = search_file_in_containers(asc_filename.stem + os.path.extsep + "asc",
                                                     # The directory where the script is located
                                                     os.path.split(self.asc_file_path)[0],
                                                     # The current script directory
                                                     os.path.curdir,
                                                     # The library paths
                                                     *self.lib_paths)
            if asc_path is None:
                raise FileNotFoundError(f"File {asc_filename} not found")
            answer = AscEditor(asc_path)
        elif symbol.symbol_type == "CELL":
            model = symbol.get_model()
            lib = symbol.get_library()
            if lib is None:
                # TODO: the library is often specified later on, so this may need to move.
                return None
            lib_path = self._lib_file_find(lib)
            if lib_path is None:
                raise FileNotFoundError(f"File {lib} not found")
            answer = SpiceEditor.find_subckt_in_lib(lib_path, model)
        else:
            raise ValueError(f"Symbol type {symbol.symbol_type} not supported")
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
        param_regex = re.compile(PARAM_REGEX(param), re.IGNORECASE)
        match, directive = self._get_directive(".PARAM", param_regex)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in ASC file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        param_regex = re.compile(PARAM_REGEX(param), re.IGNORECASE)
        match, directive = self._get_directive(".PARAM", param_regex)
        if match:
            _logger.debug(f"Parameter {param} found in ASC file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            start, stop = match.span('value')
            directive.text = f"{directive.text[:start]}{value_str}{directive.text[stop:]}"
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
        """
        Sets the value of the component

        :param device: The reference of the component
        :param value: The new value
        """
        sub_circuit, ref = self._get_parent(device)

        if sub_circuit != self:  # The component is in a subcircuit
            if isinstance(sub_circuit, SpiceCircuit):
                _logger.warning(f"Component {device} is in an Spice subcircuit. "
                                f"This function may not work as expected.")
            return sub_circuit.set_component_value(ref, value)
        else:
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
        values = [component.attributes[param_name] for param_name in ["Value", "Value2"]
                  if param_name in component.attributes]
        if len(values) == 0:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return ' '.join(values)

    def get_component_parameters(self, element: str, as_dicts: bool = False) -> dict:
        """
        Returns the parameters of a component that are related with Spice operation.
        That is: Value, Value2, SpiceModel, SpiceLine, SpiceLine2, plus all contents of SpiceLine, SpiceLine2

        :param element: Reference of the circuit element to get the parameters.
        :type element: str
        :param as_dicts: will report the contents of SpiceLine and SpiceLine2 inside a SpiceLine/SpiceLine2 instead of separately.
        :type as_dicts: bool

        :return: parameters of the circuit element in dictionary format.
        :rtype: dict

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        component = self.get_component(element)
        parameters = {}
        search_regex = re.compile(PARAM_REGEX(r'\w+'), re.IGNORECASE)
        for key, value in component.attributes.items():
            if key in LTSPICE_PARAMETERS:
                parameters[key] = value
                if key in LTSPICE_PARAMETERS_REDUCED:
                    # if we have a structured attribute, return the full dict of it
                    # this is compatible with set_component_parameters
                    sub_parameters = {}                    
                    matches = search_regex.findall(value)
                    if matches:
                        # This might contain one or more parameters
                        for param_name, param_value in matches:
                            sub_parameters[param_name] = try_convert_value(param_value)
                        if as_dicts:
                            parameters[key] = sub_parameters
                        else:
                            parameters.update(sub_parameters)

        return parameters

    def set_component_parameters(self, element: str, **kwargs) -> None:
        """
        Sets the parameters of a component that are related with Spice operation.
        That is: Value, Value2, SpiceModel, SpiceLine, SpiceLine2, or any parameters are or could be in SpiceLine, SpiceLine2.
        Other parameters are ignored.

        :param element: Reference of the circuit element to set the parameters.
        :type element: str
        """
        component = self.get_component(element)
        for key, value in kwargs.items():
            params = self.get_component_parameters(element, as_dicts=True)
            if key.lower() in (p.lower() for p in params):
                component.attributes[key] = value
                _logger.info(f"Component {element} updated with parameter {key}:{value}")
            else:
                foundme = False
                for param_key in LTSPICE_PARAMETERS_REDUCED:
                    if param_key in params:
                        params[param_key][key] = value
                        component.attributes[param_key] = ' '.join([f'{p_key}={p_value}' for p_key, p_value in params[param_key].items()])
                        _logger.info(f"Component {element} updated with parameter {key}:{value}")
                        foundme = True
                if not foundme:
                    if key.lower() in (p.lower() for p in LTSPICE_PARAMETERS):
                        # known parameter?
                        component.attributes[key] = value
                        _logger.info(f"Component {element} updated with parameter {key}:{value}")
                    else:
                        # nothing found, and not a known parameter, put it in SpiceLine
                        param_key = LTSPICE_PARAMETERS_REDUCED[0]
                        if param_key in params:
                            # if SpiceLine exists: add to the dict
                            params[param_key][key] = value
                            component.attributes[param_key] = ' '.join([f'{p_key}={p_value}' for p_key, p_value in value.items()])
                        else:
                            # if SpiceLine does not exist: create the dict
                            component.attributes[param_key] = f'{key}={value}'
                        _logger.info(f"Component {element} updated with parameter {key}:{value}")
        self.set_updated(element)

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
        file_found = search_file_in_containers(filename, *self.lib_paths)  # The library paths
        if file_found is None:
            file_found = search_file_in_containers(filename,
                                                   os.path.split(self.asc_file_path)[0],
                                                   os.path.curdir,  # The current script directory,
                                                   os.path.split(self.asc_file_path)[0],
                                                   # The directory where the script is located
                                                   os.path.expanduser("~/AppData/Local/LTspice/lib/sub"),
                                                   os.path.expanduser("~/Documents/LtspiceXVII/lib/sub"),
                                                   os.path.expanduser("~/AppData/Local/Programs/ADI/LTspice/lib.zip"),
                                                   )
        return file_found

    def _asy_file_find(self, filename) -> Optional[str]:
        if filename in self.symbol_cache:
            return self.symbol_cache[filename]
        _logger.info(f"Searching for symbol {filename}...")
        file_found = search_file_in_containers(filename, *self.lib_paths)
        if file_found is None:
            file_found = search_file_in_containers(filename,
                                                   os.path.curdir,  # The current script directory
                                                   os.path.split(self.asc_file_path)[0],
                                                   # The directory where the script is located
                                                   os.path.expanduser("~/AppData/Local/LTspice/lib/sym"),
                                                   os.path.expanduser("~/Documents/LtspiceXVII/lib/sym"),
                                                   )
        if file_found is not None:
            self.symbol_cache[filename] = file_found
        return file_found

    def add_instruction(self, instruction: str) -> None:
        # docstring inherited from BaseEditor
        instruction = instruction.strip()  # Clean any end of line terminators
        set_command = instruction.split()[0].upper()

        if set_command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            i = 0
            while i < len(self.directives):
                directive = self.directives[i]
                if directive.type == TextTypeEnum.COMMENT:
                    i += 1
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
