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
import os
from collections import OrderedDict
from pathlib import Path
from typing import Union, List, Optional, IO, TextIO
import re
import logging
from .base_editor import (
    format_eng, ComponentNotFoundError, ParameterNotFoundError,
    PARAM_REGEX, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
)
from .base_schematic import BaseSchematic, SchematicComponent, Point, ERotation, Line, Text, TextTypeEnum
from ..utils.file_search import find_file_in_directory

__all__ = ('QschEditor', )

_logger = logging.getLogger("qspice.QschEditor")

QSCH_HEADER = (255, 216, 255, 219)


# «component (-1200,-100) 0 0
QSCH_COMPONENT_POS = 1
QSCH_COMPONENT_ROTATION = 2
QSCH_COMPONENT_ENABLED = 3
#    «symbol V
#       «type: V»
#       «description: Independent Voltage Source»
#       «shorted pins: false»
#       ... primitives : rect, line, zigzag, elipse, etc...
#       «text (100,150) 1 7 0 0x1000000 -1 -1 "R1"»
#       «text (100,-150) 1 7 0 0x1000000 -1 -1 "100K"»
QSCH_SYMBOL_TEXT_REFDES = 0
QSCH_SYMBOL_TEXT_VALUE = 1
#       «pin (0,200) (0,0) 1 0 0 0x0 -1 "+"»
QSCH_SYMBOL_PIN_POS1 = 1
QSCH_SYMBOL_PIN_POS2 = 2
QSCH_SYMBOL_PIN_NET = 8
#    »
# »
#   «wire (-1200,100) (-500,100) "N01"»
QSCH_WIRE_POS1 = 1
QSCH_WIRE_POS2 = 2
QSCH_WIRE_NET = 3

# «net (<x>,<y>) <s> <l> <p> "<netname>"»
# (<x>,<y>) - Location of then Net identifier
# <s> - Font Size (1 is default)
# <l> - Location 7=Right 11=Left 13=Bottom 14=Top
#        7 0111
#       11 1011
#       13 1101
#       14 1110
# <p> - 0=Net , 1=Port
QSCH_NET_POS = 1
QSCH_NET_ROTATION = "?"
QSCH_NET_STR_ATTR = 5

#   «text (-800,-650) 1 7 0 0x1000000 -1 -1 "ï»¿.tran 5m"»
QSCH_TEXT_POS = 1
QSCH_TEXT_SIZE = 2
QSCH_TEXT_ROTATION = 3  # 13="0 Degrees" 45="90 Degrees" 77="180 Degrees" 109="270 Degrees" r= 13+32*alpha/90
QSCH_TEXT_COMMENT = 4  # 0="Normal Text" 1="Comment"
QSCH_TEXT_COLOR = 5  # 0xdbbggrr  d=1 "Default" rr=Red gg=Green bb=Blue in hex format
QSCH_TEXT_STR_ATTR = 8

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
                nested = 1
                while nested > 0:
                    i += 1
                    if stream[i] == '(':
                        nested += 1
                    elif stream[i] == ')':
                        nested -= 1
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

    def get_text(self, label, default: str = None) -> str:
        a = self.get_items(label+':')
        if len(a) != 1:
            if default is None:
                raise IndexError(f"Label '{label}' not found in:{self}")
            else:
                return default
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
    lib_paths = []  # This is a class variable, so it can be shared between all instances.

    def __init__(self, qsch_file: str, create_blank: bool = False):
        super().__init__()
        self._qsch_file_path = Path(qsch_file)
        self.schematic = None
        # read the file into memory
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        return self._qsch_file_path

    def save_as(self, qsch_filename: Union[str, Path]) -> None:
        if self.updated or Path(qsch_filename) != self._qsch_file_path:
            with open(qsch_filename, 'w', encoding="cp1252") as qsch_file:
                _logger.info(f"Writing QSCH file {qsch_file}")
                for c in QSCH_HEADER:
                    qsch_file.write(chr(c))
                qsch_file.write(self.schematic.out(0))
                qsch_file.write('\n')  # Terminates the new line
            if Path(qsch_filename) == self._qsch_file_path:
                self.updated = False
        # now checks if there are subcircuits that need to be saved
        for component in self.components.values():
            if "_SUBCKT" in component.attributes:
                sub_circuit = component.attributes["_SUBCKT"]
                if sub_circuit.updated:
                    sub_circuit.save_as(sub_circuit._qsch_file_path)

    def write_spice_to_file(self, netlist_file: TextIO):
        libraries_to_include = []
        subcircuits_to_write = OrderedDict()

        for refdes, component in self.components.items():
            component: SchematicComponent
            item_tag = component.attributes['tag']
            disabled = not component.attributes['enabled']

            symbol_tags = item_tag.get_items('symbol')
            if len(symbol_tags) != 1 or disabled:
                continue
            symbol_tag = symbol_tags[0]
            if len(symbol_tag.tokens) > 1:
                symbol = symbol_tag.get_text_attr(1)
                typ = symbol_tag.get_text('type')
            else:
                symbol = 'X'
                typ = 'X'

            texts = symbol_tag.get_items('text')
            nets = " ".join(component.ports)

            if typ in ('R', 'D', 'C', 'L', 'V', 'I'):
                value = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
                if len(texts) > 2:
                    for i in range(2, len(texts)):
                        value += ' ' + texts[i].get_text_attr(QSCH_TEXT_STR_ATTR)
                if refdes.startswith(symbol):
                    netlist_file.write(f'{refdes} {nets} {value}\n')
                else:
                    netlist_file.write(f'{symbol}†{refdes} {nets} {value}\n')
            elif typ in ('QP', 'QN', "MN", "NP"):
                model = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
                netlist_file.write(f'{refdes} {nets} 0 {model} {symbol}\n')
            elif typ == 'X':
                model = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
                parameters = ""
                if len(texts) > 2:
                    for text in texts[2:]:
                        parameters += f" {text.get_text_attr(QSCH_TEXT_STR_ATTR)}"

                # schedule to write .SUBCKT clauses at the end
                if model not in subcircuits_to_write:
                    pins = symbol_tag.get_items("pin")
                    sub_ports = " ".join(pin.get_attr(QSCH_SYMBOL_PIN_NET) for pin in pins)
                    subcircuits_to_write[model] = (
                        component.attributes['_SUBCKT'],  # the subcircuit schematic is saved
                        sub_ports,  # and also storing the port position now, so to save time later.
                    )
                netlist_file.write(f'{refdes} {nets} {model}{parameters}\n')
            else:
                _logger.error("Unsupported component type in schematic.\n"
                              f'Not Found:{typ} {refdes} {component.position}')
                netlist_file.write(f'Not Found:{typ} {refdes} {component.position}\n')

            library_tags = symbol_tag.get_items('library')
            for lib in library_tags:
                library_name = lib.get_text_attr(2)
                if library_name not in libraries_to_include:
                    libraries_to_include.append(library_name)

        for sub_circuit in subcircuits_to_write:
            sub_circuit_schematic, ports = subcircuits_to_write[sub_circuit]
            netlist_file.write("\n")
            netlist_file.write(f".subckt {sub_circuit} {ports}\n")
            sub_circuit_schematic.write_spice_to_file(netlist_file)
            netlist_file.write(f".ends {sub_circuit}\n")
            netlist_file.write("\n")

        for directive in self.directives:
            for line in directive.text.split('\\n'):
                if directive.type == TextTypeEnum.COMMENT:
                    netlist_file.write('* ')
                netlist_file.write(line.strip() + '\n')

        for library in libraries_to_include:
            library_path = self._qsch_file_find(library)
            if library_path is None:
                netlist_file.write(f'.lib {library}\n')
            else:
                from spicelib.utils.windows_short_names import get_short_path_name
                netlist_file.write(f'.lib {get_short_path_name(os.path.abspath(library_path))}\n')
        # Note: the .END or .ENDCKT must be inserted by the calling function

    def save_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)

        if self.schematic is None:
            _logger.error("Empty Schematic information")
            return
        if run_netlist_file.suffix == '.qsch':
            self.save_as(run_netlist_file)
        elif run_netlist_file.suffix in ('.net', '.cir'):
            with open(run_netlist_file, 'w') as netlist_file:
                _logger.info(f"Writing NET file {run_netlist_file}")
                netlist_file.write(f'* {os.path.abspath(self._qsch_file_path.as_posix())}\n')
                self.write_spice_to_file(netlist_file)
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
        for net in self.schematic.get_items('net'):
            if net.get_attr(1) == (x, y):
                net_name = net.get_attr(5)  # Found the net
                return '0' if net_name == 'GND' else net_name
        for wire in self.schematic.get_items('wire'):
            if wire.get_attr(1) == (x, y) or wire.get_attr(2) == (x, y):
                net_name = wire.get_attr(3)  # Found the net
                return '0' if net_name == 'GND' else net_name

        raise QschReadingError(f"Failed to find the net for {pin} in component in position {comp_pos}")

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
            x, y = position = component.get_attr(QSCH_COMPONENT_POS)
            orientation = component.get_attr(QSCH_COMPONENT_ROTATION)
            sch_comp.position = Point(x, y)
            sch_comp.rotation = orientation * 45
            sch_comp.attributes['type'] = symbol.get_text('type', "X")  # Assuming a sub-circuit
            sch_comp.attributes['description'] = symbol.get_text('description', "No Description")
            sch_comp.attributes['value'] = value
            sch_comp.attributes['tag'] = component
            sch_comp.attributes['enabled'] = component.get_attr(QSCH_COMPONENT_ENABLED) == 0
            pins = symbol.get_items('pin')
            sch_comp.ports = [self._find_net_at_pin(position, orientation, pin) for pin in pins]
            self.components[refdes] = sch_comp
            if refdes.startswith('X'):
                sub_circuit_name = value + os.path.extsep + 'qsch'
                sub_circuit_schematic_file = self._qsch_file_find(sub_circuit_name)
                sub_schematic = QschEditor(sub_circuit_schematic_file)
                sch_comp.attributes['_SUBCKT'] = sub_schematic  # Store it for future use.

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

        for text_tag in self.schematic.get_items('text'):
            x, y = text_tag.get_attr(QSCH_TEXT_POS)
            point = Point(x, y)
            text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            text_size = text_tag.get_attr(QSCH_TEXT_SIZE)
            if text_tag.get_attr(QSCH_TEXT_COMMENT) == 1:
                type_text = TextTypeEnum.COMMENT
            elif text.startswith(QSCH_TEXT_INSTR_QUALIFIER):
                type_text = TextTypeEnum.DIRECTIVE
                text = text.lstrip(QSCH_TEXT_INSTR_QUALIFIER)  # Eliminates the qualifer from the text.
            else:
                type_text = TextTypeEnum.NULL

            # angle = text_tag.get_attr(QSCH_TEXT_ROTATION)  # TODO: Implement text Rotation

            text_obj = Text(
                    point,
                    text,
                    text_size,
                    type_text,
                    # textAlignment,
                    # verticalAlignment,
                    # angle=angle,
                )
            self.directives.append(text_obj)

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

    def _qsch_file_find(self, filename) -> Optional[str]:
        for sym_root in self.lib_paths + [
            # os.path.curdir,  # The current script directory
            os.path.split(self._qsch_file_path)[0],  # The directory where the script is located
            os.path.expanduser(r"C:\Program Files\QSPICE"),
            os.path.expanduser(r"~\Documents\QSPICE"),
        ]:
            print(f"   {os.path.abspath(sym_root)}")
            if not os.path.exists(sym_root):  # Skipping invalid paths
                continue
            file_found = find_file_in_directory(sym_root, filename)
            if file_found is not None:
                return file_found
        return None

    def get_subcircuit(self, reference: str) -> 'QschEditor':
        subcircuit = self.get_component(reference)
        if '_SUBCKT' in subcircuit.attributes:  # Optimization: if it was already stored, return it
            return subcircuit.attributes['_SUBCKT']
        raise AttributeError(f"An associated subcircuit was not found for {reference}")

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
        self.updated = True

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        if isinstance(value, str):
            value_str = value
        else:
            value_str = format_eng(value)
        self.set_element_model(device, value_str)

    def set_element_model(self, device: str, model: str) -> None:
        sub_circuit, ref = self._get_parent(device)
        if ref not in sub_circuit.components:
            _logger.error(f"Component {ref} not found")
            raise ComponentNotFoundError(f"Component {ref} not found in Schematic file")

        comp = sub_circuit.get_component(ref)
        component: QschTag = comp.attributes['tag']
        symbol: QschTag = component.get_items('symbol')[0]
        texts = symbol.get_items('text')
        assert texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR) == ref
        texts[QSCH_SYMBOL_TEXT_VALUE].set_attr(QSCH_TEXT_STR_ATTR, model)
        sub_circuit.components[ref].attributes['value'] = model
        _logger.info(f"Component {device} updated to {model}")
        _logger.debug(f"Component at :{component.get_attr(1)} Updated")
        sub_circuit.updated = True

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
            rot = (rotation % 360) // 45
            if mirror:
                rot += 8
        else:
             raise ValueError("Invalid rotation parameter")

        comp_tag.set_attr(QSCH_COMPONENT_POS, position)
        comp_tag.set_attr(QSCH_COMPONENT_ROTATION, rot)
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



