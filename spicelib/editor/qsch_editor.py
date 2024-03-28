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
# Name:        qsch_editor.py
# Purpose:     Class made to update directly the QSPICE Schematic files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import math
from pathlib import Path
from typing import Union, List
import re
import logging
from .base_editor import (
    format_eng, ComponentNotFoundError, ParameterNotFoundError,
    PARAM_REGEX, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
)
from .base_schematic import BaseSchematic, SchematicComponent, Point, ERotation, Line, Text, TextTypeEnum

__all__ = ('QschEditor', )

_logger = logging.getLogger("qspice.QschEditor")

QSCH_HEADER = (255, 216, 255, 219)
QSCH_TEXT_POS = 1
QSCH_TEXT_ROTATION = 2
QSCH_TEXT_STR_ATTR = 8
QSCH_COMPONENT_POS = 1
QSCH_SYMBOL_TEXT_REFDES = 0
QSCH_SYMBOL_TEXT_VALUE = 1
QSCH_WIRE_POS1 = 1
QSCH_WIRE_POS2 = 2
QSCH_WIRE_NET = 3

# «net (<x>,<y>) <s> <l> <p> "<netname>"»
# (<x>,<y>) - Location of then Net identifier
# <s> - Font Size (1 is default)
# <l> - Location 7=Right 11=Left 13=Bottom 14=Top
# <p> - 0=Net , 1=Port

#  7 0111
# 11 1011
# 13 1101
# 14 1110

QSCH_NET_POS = 1
QSCH_NET_ROTATION = "?"
QSCH_NET_STR_ATTR = 5

QSCH_TEXT_INSTR_QUALIFIER = "ï»¿"


class QschReadingError(IOError):
    ...


class QschTag:

    def __init__(self, *tokens):
        self.items = []
        self.tokens = []
        if tokens:
            for token in tokens:
                self.tokens.append(str(token))

    @classmethod
    def parse(cls, stream: str, start: int = 0) -> ('QschTag', int):
        self = cls()
        assert stream[start] == '«'
        i = start + 1
        i0 = i
        while i < len(stream):
            if stream[i] == '«':
                child, i = QschTag.parse(stream, i)
                i0 = i + 1
                self.items.append(child)
            elif stream[i] == '»':
                stop = i + 1
                if i > i0:
                    self.tokens.append(stream[i0:i])
                return self, stop
            elif stream[i] == ' ' or stream[i] == '\n':
                if i > i0:
                    self.tokens.append(stream[i0:i])
                i0 = i + 1
            elif stream[i] == '"':
                # get all characters until the next " sign
                i += 1
                while stream[i] != '"':
                    i += 1
            elif stream[i] == '(':
                # todo: support also [] and {}
                i += 1
                nested = 1
                while nested > 0:
                    if stream[i] == '(':
                        nested += 1
                    elif stream[i] == ')':
                        nested -= 1
                    i += 1
            i += 1
        else:
            raise IOError("Missing » when reading file")

    def __str__(self):
        """Returns only the first line"""
        return ' '.join(self.tokens)

    def out(self, level):
        spaces = '  ' * level
        if len(self.items):
            return (f"{spaces}«{' '.join(self.tokens)}\n"
                    f"{''.join(tag.out(level+1) for tag in self.items)}"
                    f"{spaces}»\n")
        else:
            return f"{'  ' * level}«{' '.join(self.tokens)}»\n"

    @property
    def tag(self) -> str:
        return self.tokens[0]

    def get_items(self, item) -> List['QschTag']:
        answer = [tag for tag in self.items if tag.tag == item]
        return answer

    def get_attr(self, index: int):
        a = self.tokens[index]
        if a.startswith('(') and a.endswith(')'):
            return tuple(int(x) for x in a[1:-1].split(','))
        elif a.startswith('0x'):
            return int(a[2:], 16)
        elif a.startswith('"') and a.endswith('"'):
            return a[1:-1]
        else:
            return int(a)

    def set_attr(self, index: int, value):
        if isinstance(value, int):
            value_str = str(value)
        elif isinstance(value, str):
            if value.startswith('0x'):
                value_str = value
            else:
                value_str = f'"{value}"'
        elif isinstance(value, tuple):
            value_str = f'({value[0]},{value[1]})'
        else:
            raise ValueError("Object not supported in set_attr")
        self.tokens[index] = value_str

    def get_text(self, label) -> str:
        a = self.get_items(label+':')
        if len(a) != 1:
            raise IndexError(f"Label {label}: not found")
        return a[0].tokens[1]

    def get_text_attr(self, index: int) -> str:
        a = self.tokens[index]
        if a.startswith('"') and a.endswith('"'):
            return a[1:-1]
        else:
            return a


class QschEditor(BaseSchematic):
    """Class made to update directly QSCH files. It is a subclass of BaseSchematic, so it can be used to
    update the netlist and the parameters of the simulation. It can also be used to update the components.

    :param qsch_file: Path to the QSCH file to be edited
    :type qsch_file: str
    :keyword create_blank: If True, the file will be created from scratch. If False, the file will be read and parsed
    """

    def __init__(self, qsch_file: str, create_blank: bool = False):
        super().__init__()
        self._qsch_file_path = Path(qsch_file)
        self.schematic = None
        # read the file into memory
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        return self._qsch_file_path

    def save_as(self, qsch_file: Union[str, Path]) -> None:
        with open(qsch_file, 'w', encoding="cp1252") as qsch_file:
            _logger.info(f"Writing QSCH file {qsch_file}")
            for c in QSCH_HEADER:
                qsch_file.write(chr(c))
            qsch_file.write(self.schematic.out(0))
            qsch_file.write('\n')  # Terminates the new line

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)

        if self.schematic is None:
            _logger.error("Empty Schematic information")
            return
        if run_netlist_file.suffix == '.qsch':
            self.save_as(run_netlist_file)
        elif run_netlist_file.suffix in ('.net', '.cir'):
            libraries_to_include = []
            with open(run_netlist_file, 'w') as netlist_file:
                _logger.info(f"Writing NET file {run_netlist_file}")
                netlist_file.write(f'* Netlist generated by PyQSPICE from {self._qsch_file_path}\n')
                for item in self.schematic.items:
                    if item.tag == 'component':
                        component_pos = item.get_attr(QSCH_COMPONENT_POS)
                        orientation = item.get_attr(2)
                        disabled = item.get_attr(3)
                        symbol_tags = item.get_items('symbol')
                        if len(symbol_tags) != 1 or disabled == 1:
                            continue
                        symbol_tag = symbol_tags[0]
                        symbol = symbol_tag.get_text_attr(1)
                        typ = symbol_tag.get_text('type')
                        pins = symbol_tag.get_items('pin')
                        texts = symbol_tag.get_items('text')
                        refdes = texts[0].get_text_attr(QSCH_TEXT_STR_ATTR)
                        nets = [self._find_net_at_pin(component_pos, orientation, pin) for pin in pins]
                        if typ == 'R' or typ == 'D' or typ == 'C' or typ == 'L' or typ == 'V' or typ == 'I':
                            value = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
                            if len(texts) > 2:
                                for i in range(2, len(texts)):
                                    value += ' ' + texts[i].get_text_attr(QSCH_TEXT_STR_ATTR)
                            if refdes.startswith(symbol):
                                netlist_file.write(f'{refdes} {" ".join(nets)} {value}\n')
                            else:
                                netlist_file.write(f'{symbol}†{refdes} {" ".join(nets)} {value}\n')
                        elif typ == 'QP' or typ == 'QN':
                            model = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
                            netlist_file.write(f'{refdes} {" ".join(nets)} 0 {model} {symbol}\n')
                        else:
                            netlist_file.write(f'Not Found:{typ} {refdes} {component_pos}\n')

                        library_tags = symbol_tag.get_items('library')
                        for lib in library_tags:
                            library_name = lib.get_text_attr(2)
                            if library_name not in libraries_to_include:
                                libraries_to_include.append(library_name)
                    elif item.tag == 'text':
                        is_comment = item.get_attr(4) == 1
                        text = item.get_attr(QSCH_TEXT_STR_ATTR).lstrip(QSCH_TEXT_INSTR_QUALIFIER)
                        for line in text.split('\\n'):
                            if is_comment:
                                netlist_file.write('* ')
                            netlist_file.write(line.strip() + '\n')
                for library in libraries_to_include:
                    netlist_file.write(f'.lib {library}\n')
                netlist_file.write('.end\n')

    def _find_net_at_pin(self, comp_pos, orientation: int, pin: QschTag) -> str:
        """Returns the net at the given position"""
        pin_pos = pin.get_attr(1)
        hyp = (pin_pos[0] ** 2 + pin_pos[1] ** 2) ** 0.5
        if orientation % 2:
            # in 45º rotations the component is 1.414 times larger
            hyp *= 1.414
        if 0 <= orientation <= 7:
            theta = math.atan2(pin_pos[1], pin_pos[0]) + math.radians(orientation * 45)
            x = comp_pos[0] + round(hyp * math.cos(theta), -2)  # round to multiple of 100
            y = comp_pos[1] + round(hyp * math.sin(theta), -2)
        elif 8 <= orientation <= 15:
            # The component is mirrored on the X axis
            theta = math.atan2(pin_pos[1], pin_pos[0]) + math.radians((orientation - 8) * 45)
            x = comp_pos[0] - round(hyp * math.cos(theta), -2)  # round to multiple of 100
            y = comp_pos[1] + round(hyp * math.sin(theta), -2)
        else:
            raise ValueError(f"Invalid orientation: {orientation}")
        for net in self.schematic.get_items('wire'):
            if net.get_attr(1) == (x, y) or net.get_attr(2) == (x, y):
                net_name = net.get_attr(3)  # Found the net
                return '0' if net_name == 'GND' else net_name
        else:
            return '####'

    def reset_netlist(self, create_blank: bool = False) -> None:
        """Reads the QSCH file and parses it into memory.

        :param create_blank: If True, the file will be created from scratch. If False, the file will be read and parsed
        """
        super().reset_netlist(create_blank)
        if not create_blank:
            if not self._qsch_file_path.exists():
                raise FileNotFoundError(f"File {self._qsch_file_path} not found")
            with open(self._qsch_file_path, 'r', encoding="cp1252") as qsch_file:
                _logger.info(f"Reading QSCH file {self._qsch_file_path}")
                stream = qsch_file.read()
            self._parse_qsch_stream(stream)

    def _parse_qsch_stream(self, stream):

        self.components.clear()
        _logger.debug("Parsing QSCH file")
        header = tuple(ord(c) for c in stream[:4])

        if header != QSCH_HEADER:
            raise QschReadingError("Missing header. The QSCH file should start with: " +
                                   f"{' '.join(f'{c:02X}' for c in QSCH_HEADER)}")

        schematic, _ = QschTag.parse(stream, 4)
        self.schematic = schematic

        components = self.schematic.get_items('component')
        for component in components:
            symbol: QschTag = component.get_items('symbol')[0]
            texts = symbol.get_items('text')
            if len(texts) < 2:
                raise RuntimeError(f"Missing texts in component at coordinates {component.get_attr(1)}")
            refdes = texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR)
            value = texts[QSCH_SYMBOL_TEXT_VALUE].get_attr(QSCH_TEXT_STR_ATTR)
            sch_comp = SchematicComponent()
            sch_comp.reference = refdes
            x, y = tuple(component.get_attr(QSCH_COMPONENT_POS))
            sch_comp.position = Point(x, y)
            sch_comp.rotation = component.get_attr(QSCH_TEXT_ROTATION) / 45
            sch_comp.attributes['type'] = symbol.get_text('type')
            sch_comp.attributes['description'] = symbol.get_text('description'),
            sch_comp.attributes['value'] = value
            sch_comp.attributes['tag'] = component
            self.components[refdes] = sch_comp

        for net in self.schematic.get_items('net'):
            # process nets
            x, y = net.get_attr(QSCH_NET_POS)
            # TODO: Get the remaining attributes Rotation, size, color, etc...
            # rotation = net.get_attr(QSCH_NET_ROTATION)
            net_name = net.get_attr(QSCH_NET_STR_ATTR)
            self.labels.append(Text(Point(x, y), net_name, type=TextTypeEnum.LABEL))

        for wire in self.schematic.get_items('wire'):
            # process wires
            x1, y1 = wire.get_attr(QSCH_WIRE_POS1)
            x2, y2 = wire.get_attr(QSCH_WIRE_POS2)
            net = wire.get_attr(QSCH_WIRE_NET)
            self.wires.append(Line(Point(x1, y1), Point(x2, y2), net))

    def _get_text_matching(self, command, search_expression: re.Pattern):
        command_upped = command.upper()
        text_tags = self.schematic.get_items('text')
        for tag in text_tags:
            line = tag.get_attr(QSCH_TEXT_STR_ATTR)
            line = line.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
            if line.upper().startswith(command_upped):
                match = search_expression.search(line)
                if match:
                    return tag, match
        else:
            return None, None

    def get_parameter(self, param: str) -> str:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in QSCH file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            _logger.debug(f"Parameter {param} found in QSCH file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            text: str = tag.get_attr(QSCH_TEXT_STR_ATTR)
            match = param_regex.search(text)  # repeating the search, so we update the correct start/stop parameter
            start, stop = match.span(param_regex.groupindex['replace'])
            text = text[:start] + "{}={}".format(param, value_str) + text[stop:]
            tag.set_attr(QSCH_TEXT_STR_ATTR, text)
            _logger.info(f"Parameter {param} updated to {value_str}")
            _logger.debug(f"Text at {tag.get_attr(QSCH_TEXT_POS)} Updated to {text}")
        else:
            # Was not found so we need to add it,
            _logger.debug(f"Parameter {param} not found in QSCH file, adding it")
            x, y = self._get_text_space()
            tag, _ = QschTag.parse(
                f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 "{QSCH_TEXT_INSTR_QUALIFIER}.param {param}={value}"»'
            )
            self.schematic.items.append(tag)
            _logger.info(f"Parameter {param} added with value {value}")
            _logger.debug(f"Text added to {tag.get_attr(QSCH_TEXT_POS)} Added: {tag.get_attr(QSCH_TEXT_STR_ATTR)}")

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        if isinstance(value, str):
            value_str = value
        else:
            value_str = format_eng(value)
        self.set_element_model(device, value_str)

    def set_element_model(self, device: str, model: str) -> None:
        comp = self.get_component(device)
        component: QschTag = comp.attributes['tag']
        symbol: QschTag = component.get_items('symbol')[0]
        texts = symbol.get_items('text')
        assert texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR) == device
        texts[QSCH_SYMBOL_TEXT_VALUE].set_attr(QSCH_TEXT_STR_ATTR, model)
        self.components[device].attributes['value'] = model
        _logger.info(f"Component {device} updated to {model}")
        _logger.debug(f"Component at :{component.get_attr(1)} Updated")

    def get_component_value(self, element: str) -> str:
        component = self.get_component(element)
        if "value" not in component.attributes:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return component.attributes["value"]

    def get_component_position(self, reference: str) -> (Point, ERotation):
        component = self.get_component(reference)
        return component.position, component.rotation

    def set_component_position(self, reference: str,
                               position: Union[Point, tuple],
                               rotation: Union[ERotation, int],
                               mirror: bool = False,
                               ) -> None:
        component = self.get_component(reference)
        comp_tag: QschTag = component.attributes['tag']
        if isinstance(position, tuple):
            position = (position[0], position[1])
        elif isinstance(position, Point):
            position = (position.X, position.Y)
        else:
            raise ValueError("Invalid position object")
        if isinstance(rotation, ERotation):
            rot = rotation.value / 45
        elif isinstance(rotation, int):
            if mirror is False:
                rot = {
                    0: 0,
                    45: 1,
                    90: 2,
                    135: 3,
                    180: 4,
                    225: 5,
                    270: 6,
                    315: 7,
                }[rotation % 360]
            else:
                rot = {
                    0: 8,
                    45: 9,  # 45º rotation is valid for QSpice Schematics Files
                    90: 10,
                    135: 11,
                    180: 12,
                    225: 13,
                    270: 14,
                    315: 15,
                }[rotation % 360]
        else:
             raise ValueError("Invalid rotation parameter")

        comp_tag.set_attr(QSCH_COMPONENT_POS, position)
        comp_tag.set_attr(QSCH_TEXT_ROTATION, rot)
        component.position = position
        component.rotation = rotation

    def get_components(self, prefixes='*') -> list:
        if prefixes == '*':
            return list(self.components.keys())
        return [k for k in self.components.keys() if k[0] in prefixes]

    def remove_component(self, designator: str):
        component = self.get_component(designator)
        comp_tag: QschTag = component.attributes['tag']
        self.schematic.items.remove(comp_tag)

    def _get_text_space(self):
        """
        Returns the coordinate on the Schematic File canvas where a text can be appended.
        """
        first = True
        for tag in self.schematic.items:
            if tag.tag in ('component', 'net', 'text'):
                x1, y1 = tag.get_attr(1)
                x2, y2 = x1, y1  # todo: the whole component primitives
            elif tag.tag == 'wire':
                x1, y1 = tag.get_attr(1)
                x2, y2 = tag.get_attr(2)
            else:
                continue  # this avoids executing the code below when no coordinates are found
            if first:
                min_x = min(x1, x2)
                max_x = max(x1, x2)
                min_y = min(y1, y2)
                max_y = max(y1, y2)
                first = False
            else:
                min_x = min(min_x, x1, x2)
                max_x = max(max_x, x1, x2)
                min_y = min(min_y, y1, y2)
                max_y = max(max_y, y1, y2)

        if first:
            return 0, 0  # If no coordinates are found, we return the origin
        else:
            return min_x, min_y - 240  # Setting the text in the bottom left corner of the canvas

    def add_instruction(self, instruction: str) -> None:
        instruction = instruction.strip()  # Clean any end of line terminators
        command = instruction.split()[0].upper()

        if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            for text_tag in self.schematic.get_items('text'):
                text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
                text = text.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
                command = text.split()[0].upper()
                if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
                    text_tag.set_attr(QSCH_TEXT_STR_ATTR, QSCH_TEXT_INSTR_QUALIFIER + instruction)
                    return  # Job done, can exit this method

        elif command.startswith('.PARAM'):
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')
        # If we get here, then the instruction was not found, so we need to add it
        x, y = self._get_text_space()
        tag, _ = QschTag.parse(f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 "{QSCH_TEXT_INSTR_QUALIFIER}{instruction}"»')
        self.schematic.items.append(tag)

    def remove_instruction(self, instruction: str) -> None:
        for text_tag in self.schematic.get_items('text'):
            text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            if instruction in text:
                self.schematic.items.remove(text_tag)
                _logger.info(f'Instruction "{instruction}" removed')
                return  # Job done, can exit this method

        msg = f'Instruction "{instruction}" not found'
        _logger.error(msg)

    def remove_Xinstruction(self, search_pattern: str) -> None:
        regex = re.compile(search_pattern, re.IGNORECASE)
        instr_removed = False
        for text_tag in self.schematic.get_items('text'):
            text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            text = text.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
            if regex.match(text):
                self.schematic.items.remove(text_tag)
                _logger.info(f'Instruction "{text}" removed')
                instr_removed = True
        if not instr_removed:
            msg = f'Instruction matching "{search_pattern}" not found'
            _logger.error(msg)

    def copy_from(self, editor: 'BaseSchematic') -> None:
        super().copy_from(editor)
        # We need to copy the schematic information
        if isinstance(editor, QschEditor):
            from copy import deepcopy
            self.schematic = deepcopy(editor.schematic)
        else:
            # Need to create a new schematic from the netlist
            self.schematic = QschTag('schematic')
            for ref, comp in self.components.items():
                cmpx = comp.position.X
                cmpy = comp.position.Y
                rotation = int(comp.rotation) // 45
                comp_tag, _ = QschTag.parse(f'«component ({cmpx},{cmpy}) {rotation} 0»')
                if 'symbol' in comp.attributes:
                    comp_tag.items.append(comp.attributes['symbol'])
                self.schematic.items.append(comp_tag)

            for labels in self.labels:
                label_tag, _ = QschTag.parse('«net (0,0) 1 13 0 "0"»')
                label_tag.set_attr(QSCH_NET_STR_ATTR, labels.text)
                label_tag.set_attr(QSCH_NET_POS, (labels.coord.X, labels.coord.Y))
                self.schematic.items.append(label_tag)

            for wire in self.wires:
                wire_tag, _ = QschTag.parse('«wire (0,0) (0,0) "0"»')
                wire_tag.set_attr(QSCH_WIRE_POS1, (wire.V1.X, wire.V1.Y))
                wire_tag.set_attr(QSCH_WIRE_POS2, (wire.V2.X, wire.V2.Y))
                # wire_tag.set_attr(QSCH_WIRE_NET, wire.net)
                self.schematic.items.append(wire_tag)

            for text in self.directives:
                text_tag, _ = QschTag.parse('«text (0,0) 1 7 0 0x1000000 -1 -1 "text"»')
                text_tag.set_attr(QSCH_TEXT_STR_ATTR, QSCH_TEXT_INSTR_QUALIFIER + text.text)
                text_tag.set_attr(QSCH_TEXT_POS, (text.coord.X, text.coord.Y))
                self.schematic.items.append(text_tag)



