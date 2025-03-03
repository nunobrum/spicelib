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
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Union, List, Optional, TextIO, Tuple
import re
import logging
from .base_editor import (
    format_eng, ComponentNotFoundError, ParameterNotFoundError,
    PARAM_REGEX, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
)
from .base_schematic import (BaseSchematic, SchematicComponent, Point, ERotation, Line, Text, TextTypeEnum,
                             LineStyle, Shape)
from ..simulators.qspice_simulator import Qspice
from ..utils.file_search import search_file_in_containers

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

__all__ = ('QschEditor', 'QschTag', 'QschReadingError')

_logger = logging.getLogger("spicelib.QschEditor")

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
QSCH_SYMBOL_PIN_NET_BEHAVIORAL = 9
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

#   «text (-800,-650) 1 77 0 0x1000000 -1 -1 "ï»¿.tran 5m"»
QSCH_TEXT_POS = 1
QSCH_TEXT_SIZE = 2
QSCH_TEXT_ROTATION = 3  # 13="0 Degrees" 45="90 Degrees" 77="180 Degrees" 109="270 Degrees" r= 13+32*alpha/90
QSCH_TEXT_COMMENT = 4  # 0="Normal Text" 1="Comment"
QSCH_TEXT_COLOR = 5  # 0xdbbggrr  d=1 "Default" rr=Red gg=Green bb=Blue in hex format
QSCH_TEXT_STR_ATTR = 8

QSCH_TEXT_INSTR_QUALIFIER = "ï»¿"

# «line (2000,1300) (3150,-100) 1 1 0xff0000 -1 -1»
QSCH_LINE_POS1 = 1
QSCH_LINE_POS2 = 2
QSCH_LINE_WIDTH = 3  # 0=Default 1=Thinnest ... 7=Thickest
QSCH_LINE_TYPE = 4  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_LINE_COLOR = 5
QSCH_LINE_UNKNOWN1 = 6
QSCH_LINE_UNKNOWN2 = 7

# «rect (1850,1550) (3650,-400) 0 0 0 0x8000 0x1000000 -1 0 -1»
QSCH_RECT_POS1 = 1
QSCH_RECT_POS2 = 2
QSCH_RECT_UNKNOWN0 = 3
QSCH_RECT_LINE_WIDTH = 4
QSCH_RECT_LINE_TYPE = 5  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_RECT_LINE_COLOR = 6
QSCH_RECT_FILL_COLOR = 7
QSCH_RECT_UNKNOWN1 = 8
QSCH_RECT_UNKNOWN2 = 9
QSCH_RECT_UNKNOWN3 = 10

#  «ellipse (2100,1150) (2650,150) 0 0 2 0xff0000 0x1000000 -1 -1»
QSCH_ELLIPSE_POS1 = 1
QSCH_ELLIPSE_POS2 = 2
QSCH_ELLIPSE_UNKNOWN0 = 3
QSCH_ELLIPSE_WIDTH = 4
QSCH_ELLIPSE_LINE_TYPE = 5  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_ELLIPSE_LINE_COLOR = 6
QSCH_ELLIPSE_FILL_COLOR = 7
QSCH_ELLIPSE_UNKNOWN1 = 8
QSCH_ELLIPSE_UNKNOWN2 = 9

# «arc3p (2700,300) (2250,1200) (2500,800) 0 2 0xff0000 -1 -1»
QSCH_ARC3P_POS1 = 1
QSCH_ARC3P_POS2 = 2
QSCH_ARC3P_POS3 = 3
QSCH_ARC3P_UNKNOWN0 = 4
QSCH_ARC3P_WIDTH = 5
QSCH_ARC3P_LINE_COLOR = 6
QSCH_ARC3P_UNKNOWN1 = 7
QSCH_ARC3P_UNKNOWN2 = 8

# «triangle (3050,1250) (3550,700) (3450,1400) 0 2 0xff0000 0x2000000 -1 -1»
QSCH_TRIANGLE_POS1 = 1
QSCH_TRIANGLE_POS2 = 2
QSCH_TRIANGLE_POS3 = 3
QSCH_TRIANGLE_UNKNOWN0 = 4
QSCH_TRIANGLE_LINE_TYPE = 5  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_TRIANGLE_LINE_COLOR = 6
QSCH_TRIANGLE_FILL_COLOR = 7
QSCH_TRIANGLE_UNKNOWN1 = 8
QSCH_TRIANGLE_UNKNOWN2 = 9

# «coil (3050,400) (3450,600) 0 0 2 0xff0000 -1 -1»
QSCH_COIL_POS1 = 1
QSCH_COIL_POS2 = 2
QSCH_COIL_UNKNOWN0 = 3
QSCH_COIL_WIDTH = 4
QSCH_COIL_LINE_TYPE = 5  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_COIL_LINE_COLOR = 6
QSCH_COIL_UNKNOWN1 = 7
QSCH_COIL_UNKNOWN2 = 8

# «zigzag (3050,250) (3400,100) 0 0 2 0xff0000 -1 -1»
QSCH_ZIGZAG_POS1 = 1
QSCH_ZIGZAG_POS2 = 2
QSCH_ZIGZAG_UNKNOWN0 = 3
QSCH_ZIGZAG_WIDTH = 4
QSCH_ZIGZAG_LINE_TYPE = 5  # 0=Normal 1=Dashed 2=Dotted 3=DashDot 4=DashDotDot
QSCH_ZIGZAG_LINE_COLOR = 6
QSCH_ZIGZAG_UNKNOWN1 = 7
QSCH_ZIGZAG_UNKNOWN2 = 8


def decap(s: str) -> str:
    """Take the leading < and ending > from the parameter value on a string with the format "param=<value>"
    If they are not there, the string is returned unchanged."""
    regex = re.compile(r"(\w+)=<(.*)>")
    return regex.sub(r"\1=\2", s)


def smart_split(s):
    """Splits a string into chunks based on spaces. What is inside "" is not divided."""
    return re.findall(r'[^"\s]+|"[^"]*"', s)


class QschReadingError(IOError):
    ...


class QschTag:
    """
    Class to represent a tag in a QSCH file. It is a recursive class, so it can have children tags.
    """

    def __init__(self, *tokens):
        self.items = []
        self.tokens = []
        if tokens:
            for token in tokens:
                self.tokens.append(str(token))

    @classmethod
    def parse(cls, stream: str, start: int = 0) -> Tuple['QschTag', int]:
        """
        Parses a tag from the stream starting at the given position. The stream should be a string.

        :param stream: The string to be parsed
        :param start: The position to start parsing
        :return: A tuple with the tag and the position after the tag
        """
        self = cls()
        assert stream[start] == '«'
        i = start + 1
        i0 = i
        while i < len(stream):
            if stream[i] == '«':
                child, i = QschTag.parse(stream, i)
                i0 = i + 1
                self.items.append(child)
            elif stream[i] == '"':
                # get all characters until the next " sign
                i += 1
                while stream[i] != '"':
                    i += 1
            elif stream[i] == '»':
                stop = i + 1
                break
            elif stream[i] == '\n':
                if i > i0:
                    tokens = smart_split(stream[i0:i])
                    self.tokens.extend(tokens)
                i0 = i + 1
            i += 1
        else:
            raise IOError("Missing » when reading file")
        line = stream[i0:i]
        # Now dividing the
        if ': ' in line:
            name, text = line.split(': ')
            self.tokens.append(name + ":")
            self.tokens.append(text)
        else:
            self.tokens.extend(smart_split(line))
        return self, stop

    def __str__(self):
        """Returns only the first line of the tag. The children are not shown."""
        return ' '.join(self.tokens)

    def out(self, level):
        """
        Returns a string representation of the tag with the specified indentation.

        :param level: The indentation level
        :return: A string representation of the tag
        """
        spaces = '  ' * level
        if len(self.items):
            return (f"{spaces}«{' '.join(self.tokens)}\n"
                    f"{''.join(tag.out(level + 1) for tag in self.items)}"
                    f"{spaces}»\n")
        else:
            return f"{'  ' * level}«{' '.join(self.tokens)}»\n"

    @property
    def tag(self) -> str:
        """Returns the tag id of the object. The tag id is the first token in the tag."""
        return self.tokens[0]
    
    def get_items(self, item) -> List['QschTag']:
        """Returns a list of children tags that match the given tag id."""
        answer = [tag for tag in self.items if tag.tag == item]
        return answer

    def get_attr(self, index: int):
        """
        Returns the attribute at the given index. The attribute can be a string, an integer or a tuple.
        The return type depends on the attribute being read.
        If the attribute is between quotes, it returns a string.
        If it is between parenthesis, it returns a tuple of integers.
        If it starts with "0x", it returns an integer representing the following hexadecimal number.
        Otherwise, it returns an integer.

        :param index: The index of the attribute to be read
        :type index: int
        :return: The attribute at the given index
        """
        a = self.tokens[index]
        if a.startswith('(') and a.endswith(')'):
            return tuple(int(x) for x in a[1:-1].split(','))
        elif a.startswith('0x'):
            return int(a[2:], 16)
        elif a.startswith('"') and a.endswith('"'):
            return a[1:-1]
        else:
            try:
                value = int(a)
            except ValueError:
                try:
                    value = float(a)
                except ValueError:
                    value = a
            return value

    def set_attr(self, index: int, value: Union[str, int, tuple]):
        """Sets the attribute at the given index. The attribute can be a string, an integer or a tuple.
        Integer values are written as integers, strings are written between quotes unless it starts with "0x"
        and tuples are written between parenthesis.

        :param index: The index of the attribute to be set
        :type index: int
        :param value: The value to be set
        :type value: Union[str, int, Tuple[Any, Any]]
        :return: Nothing
        """
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

    def get_text(self, label: str, default: str = None) -> str:
        """
        Returns the text of the first child tag that matches the given label. The label can have up to 1 space in it.
        It will return the entire text of the tag, after the label.
        If the label is not found, it returns the default value.

        :param label: label to be found. Can have up to 1 space (e.g. "library file" or "shorted pins")
        :type label: str
        :param default: Default value, defaults to None
        :type default: str, optional
        :raises IndexError: When the label is not found and the default value is None
        :return: the found text or the default value
        :rtype: str
        """
        a = self.get_items(label + ':')
        if len(a) != 1:
            if default is None:
                raise IndexError(f"Label '{label}' not found in:{self}")
            else:
                return default
        if len(a[0].tokens) >= 2:
            return a[0].tokens[1]
        else:
            return default

    def get_text_attr(self, index: int) -> str:
        """Returns the text of the attribute at the given index. Unlike get_attr, this method only returns strings."""
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

    simulator_lib_paths: List[str] = Qspice.get_default_library_paths()    
    """ This is initialised with typical locations found for QSPICE.
    You can (and should, if you use wine), call `prepare_for_simulator()` once you've set the executable paths.
    This is a class variable, so it will be shared between all instances.
    
    :meta hide-value:
    """    

    def __init__(self, qsch_file: str, create_blank: bool = False):
        super().__init__()
        self._qsch_file_path = Path(qsch_file)
        self.schematic = None
        # read the file into memory
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        # docstring inherited from BaseSchematic
        return self._qsch_file_path

    def save_as(self, qsch_filename: Union[str, Path]) -> None:
        """
        Saves the schematic to a QSCH file. The file is saved in cp1252 encoding.
        """
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
                sub_circuit = component.attributes['_SUBCKT']
                if sub_circuit is not None and sub_circuit.updated:
                    sub_circuit.save_as(sub_circuit._qsch_file_path)

    def write_spice_to_file(self, netlist_file: TextIO):
        """
        Appends the netlist to a file buffer.

        :param netlist_file: The file buffer to save the netlist
        :type netlist_file: TextIO
        :return: Nothing
        """
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

            if refdes[0] != typ[0]:
                refdes = typ[0] + '´' + refdes

            texts = symbol_tag.get_items('text')
            parameters = ""
            if len(texts) > 2:
                for text in texts[2:]:
                    parameters += " " + decap(text.get_text_attr(QSCH_TEXT_STR_ATTR))

            ports = component.ports.copy()
            if typ in ('¥', 'Ã'):
                if len(ports) < 16:
                    ports += ['¥'] * (16 - len(ports))

            nets = " ".join(ports)
            model = texts[1].get_text_attr(QSCH_TEXT_STR_ATTR)
            
            # Check the libraries and embedded subcircuits
            library_name = symbol_tag.get_text('library file', default="")
            if library_name.startswith('|'):
                # make a regular expression that will prefix the model or subcircuit with {refdes}•{model}
                new_line = re.sub(r"^\|\.(model|subckt) (\w+) (.*)",
                                  fr".\1 {refdes}•\2 \3",
                                  library_name, re.MULTILINE)
                new_line = new_line.replace("\\n", "\n")
                netlist_file.write(new_line+'\n')
                model = f"{refdes}•{model}"
            elif library_name and (library_name not in libraries_to_include):
                # List the libraries at the end
                libraries_to_include.append(library_name)

            if typ == 'X':
                # schedule to write .SUBCKT clauses at the end
                if model not in subcircuits_to_write:
                    if '_SUBCKT' in component.attributes:
                        pins = symbol_tag.get_items("pin")
                        sub_ports = " ".join(pin.get_attr(QSCH_SYMBOL_PIN_NET) for pin in pins)
                        subcircuits_to_write[model] = (
                            component.attributes['_SUBCKT'],  # the subcircuit schematic is saved
                            sub_ports,  # and also storing the port position now, so to save time later.
                        )
                nets = " ".join(component.ports)
                netlist_file.write(f'{refdes} {nets} {model}{parameters}\n')

            elif typ in ('QP', 'QN'):
                if symbol == 'NPNS' or symbol == 'PNPS' or symbol == 'LPNP':
                    ports[3] = '[' + ports[3] + ']'
                    nets = ' '.join(ports)
                    hack = 'PNP' if 'PNP' in symbol else 'NPN'
                    netlist_file.write(f'{refdes} {nets} {model} {hack}{parameters}\n')
                else:
                    netlist_file.write(f'{refdes} {nets} [0] {model} {symbol}{parameters}\n')
            elif typ in ('MN', 'MP'):
                if symbol == 'NMOSB' or symbol == 'PMOSB':
                    symbol = symbol[0:4]
                if len(ports) == 3:
                    netlist_file.write(f'{refdes} {nets} {ports[2]} {model} {symbol}{parameters}\n')
                else:
                    netlist_file.write(f'{refdes} {nets} {model} {symbol}{parameters}\n')
            elif typ == 'T':
                model = decap(texts[1].get_text_attr(QSCH_TEXT_STR_ATTR))
                netlist_file.write(f'{refdes} {nets} {model}{parameters}\n')
            elif typ in ('JN', 'JP'):
                if symbol.startswith('Pwr'):  # Hack alert. I don't know why the symbol is Pwr
                    symbol = symbol[3:]  # remove the Pwr from the symbol
                netlist_file.write(f'{refdes} {nets} {model} {symbol}{parameters}\n')
            elif typ == '×':
                netlist_file.write(f'{refdes} «{nets}» {model}{parameters}\n')
            elif typ in ('ZP', 'ZN'):
                netlist_file.write(f'{refdes} {nets} {model} {symbol}{parameters}\n')
            else:
                netlist_file.write(f'{refdes} {nets} {model}{parameters}\n')

        for sub_circuit in subcircuits_to_write:
            sub_circuit_schematic, ports = subcircuits_to_write[sub_circuit]
            netlist_file.write("\n")
            netlist_file.write(f".subckt {sub_circuit} {ports}\n")
            sub_circuit_schematic.write_spice_to_file(netlist_file)
            netlist_file.write(f".ends {sub_circuit}\n")
            netlist_file.write("\n")

        text_tags = self.schematic.get_items('text')
        for text_tag in text_tags:
            lines = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            lines = lines.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
            for line in lines.split('\\n'):
                if text_tag.get_attr(QSCH_TEXT_COMMENT) != 1:  # Comments are not written to the netlist
                    netlist_file.write(line.strip() + '\n')

        for library in libraries_to_include:
            mydir = self.circuit_file.parent.absolute().as_posix()
            library_path = self._qsch_file_find(library, mydir)
            if library_path is None:
                netlist_file.write(f'.lib {library}\n')
            else:
                if sys.platform.startswith("win"):
                    from spicelib.utils.windows_short_names import get_short_path_name
                    netlist_file.write(f'.lib {get_short_path_name(os.path.abspath(library_path))}\n')
                else:
                    netlist_file.write(f'.lib {os.path.abspath(library_path)}\n')

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
            with open(run_netlist_file, 'w', encoding="cp1252") as netlist_file:
                _logger.info(f"Writing NET file {run_netlist_file}")
                netlist_file.write(f'* {os.path.abspath(self._qsch_file_path.as_posix())}\n')
                self.write_spice_to_file(netlist_file)
                netlist_file.write('.end\n')

    def _find_pin_position(self, comp_pos, orientation: int, pin: QschTag) -> Tuple[int, int]:
        """Returns the net name at the pin position"""
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
        return x, y

    def _find_net_at_position(self, x, y) -> Optional[str]:
        """Returns the net name at the given position"""
        for net in self.schematic.get_items('net'):  # Connection to ports, grounds and nets
            if net.get_attr(1) == (x, y):
                net_name = net.get_attr(5)  # Found the net
                return '0' if net_name == 'GND' else net_name
        for wire in self.schematic.get_items('wire'):  # Connection to wires
            if wire.get_attr(1) == (x, y) or wire.get_attr(2) == (x, y):
                net_name = wire.get_attr(3)  # Found the net
                return '0' if net_name == 'GND' else net_name
        return None

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        If create_blank is True, it creates a blank netlist.

        If False, it reads the netlist from the file into memory. If the file does not exist, it raises a FileNotFoundError.

        All previous edits done to the netlist are lost.

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
        """Parses the QSCH file stream"""
        self.components.clear()
        _logger.debug("Parsing QSCH file")
        header = tuple(ord(c) for c in stream[:4])

        if header != QSCH_HEADER:
            raise QschReadingError("Missing header. The QSCH file should start with: " +
                                   f"{' '.join(f'{c:02X}' for c in QSCH_HEADER)}")

        schematic, _ = QschTag.parse(stream, 4)
        self.schematic = schematic
        highest_net_number = 0
        behavior_pin_counter = 0
        unconnected_pins = {}  # Storing the components that have floating pins

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
            # Check if the net is of the format N##, if it is get the net number
            if net.startswith('N'):
                try:
                    net_no = int(net[1:])
                    if net_no > highest_net_number:
                        highest_net_number = net_no
                except ValueError:
                    pass
            self.wires.append(Line(Point(x1, y1), Point(x2, y2), net=net))

        components = self.schematic.get_items('component')
        for component in components:
            have_embedded_subcircuit = False
            symbol: QschTag = component.get_items('symbol')[0]
            texts = symbol.get_items('text')
            if len(texts) < 2:
                raise RuntimeError(f"Missing texts in component at coordinates {component.get_attr(1)}")
            refdes = texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR)
            value = texts[QSCH_SYMBOL_TEXT_VALUE].get_attr(QSCH_TEXT_STR_ATTR)
            sch_comp = SchematicComponent(self, refdes)
            sch_comp.reference = refdes
            x, y = position = component.get_attr(QSCH_COMPONENT_POS)
            orientation = component.get_attr(QSCH_COMPONENT_ROTATION)
            sch_comp.position = Point(x, y)
            sch_comp.rotation = orientation * 45
            sch_comp.attributes['type'] = symbol.get_text('type', "X")  # Assuming a sub-circuit
            # a bit complicated way to detect embedded subcircuits: they are in the library tag,
            lib = symbol.get_text('library file', "-")
            if lib.startswith("|.subckt"):
                have_embedded_subcircuit = True
            sch_comp.attributes['description'] = symbol.get_text('description', "No Description")
            sch_comp.attributes['value'] = value
            sch_comp.attributes['tag'] = component
            sch_comp.attributes['enabled'] = component.get_attr(QSCH_COMPONENT_ENABLED) == 0
            sch_comp.ports = []
            pins = symbol.get_items('pin')

            for pin in pins:
                x, y = self._find_pin_position(position, orientation, pin)
                net = self._find_net_at_position(x, y)
                # The pins that have "¥" are behavioral pins, they are not connected to any net, they will be connected
                # to a net later.
                if refdes[0] in ('¥', 'Ã'):
                    if (len(pin.tokens) > QSCH_SYMBOL_PIN_NET_BEHAVIORAL and
                            pin.get_attr(QSCH_SYMBOL_PIN_NET_BEHAVIORAL) == '¥'):
                        net = '¥'
                if net is None:
                    hash_key = (x, y)
                    if hash_key in unconnected_pins:
                        net = unconnected_pins[hash_key]
                    else:
                        _logger.info(f"Unconnected pin at {x},{y} in component {refdes}:{pin}")
                        if refdes[0] in ('¥', 'Ã'):  # Behavioral pins are not connected
                            net = f'¥{behavior_pin_counter:d}'
                            behavior_pin_counter += 1
                        else:
                            highest_net_number += 1
                            net = f'N{highest_net_number:02d}'
                        unconnected_pins[hash_key] = net
                sch_comp.ports.append(net)

            self.components[refdes] = sch_comp
            if refdes.startswith('X'):
                if not have_embedded_subcircuit:
                    sub_circuit_name = value + os.path.extsep + 'qsch'
                    mydir = self.circuit_file.parent.absolute().as_posix()
                    sub_circuit_schematic_file = self._qsch_file_find(sub_circuit_name, mydir)
                    if sub_circuit_schematic_file:
                        sub_schematic = QschEditor(sub_circuit_schematic_file)
                        sch_comp.attributes['_SUBCKT'] = sub_schematic  # Store it for future use.
                    else:
                        _logger.warning(f"Subcircuit '{sub_circuit_name}' not found. Have you set the correct search paths?")

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

        for line_tag in self.schematic.get_items('line'):
            x1, y1 = line_tag.get_attr(QSCH_LINE_POS1)
            x2, y2 = line_tag.get_attr(QSCH_LINE_POS2)
            width = line_tag.get_attr(QSCH_LINE_WIDTH)
            line_type = line_tag.get_attr(QSCH_LINE_TYPE)
            color = line_tag.get_attr(QSCH_LINE_COLOR)
            line = Line(Point(x1, y1), Point(x2, y2))
            line.style = LineStyle(width, line_type, color)
            self.lines.append(line)

    def _get_param_named(self, param_name):
        param_regex = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        param_name_upped = param_name.upper()
        text_tags = self.schematic.get_items('text')
        for tag in text_tags:
            line = tag.get_attr(QSCH_TEXT_STR_ATTR)
            line = line.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
            if line.upper().startswith('.PARAM'):
                for match in param_regex.finditer(line):
                    if match.group("name").upper() == param_name_upped:
                        return tag, match
        else:
            return None, None
        
    def get_all_parameter_names(self) -> List[str]:
        # docstring inherited from BaseEditor
        param_names = []
        param_regex = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        text_tags = self.schematic.get_items('text')
        for tag in text_tags:
            line = tag.get_attr(QSCH_TEXT_STR_ATTR)
            line = line.lstrip(QSCH_TEXT_INSTR_QUALIFIER)
            if line.upper().startswith('.PARAM'):
                matches = param_regex.finditer(line)
                for match in matches:
                    param_name = match.group('name')
                    param_names.append(param_name.upper())
        return sorted(param_names)

    def _qsch_file_find(self, filename: str, work_dir: str = None) -> Optional[str]:
        containers = ['.'] + self.custom_lib_paths + self.simulator_lib_paths
        # '.'  is the directory where the script is located
        if (work_dir is not None) and work_dir != ".":
            containers = [work_dir] + containers  # put work directory first
        return search_file_in_containers(filename, *containers)

    def get_subcircuit(self, reference: str) -> 'QschEditor':
        """Returns an QschEditor file corresponding to the symbol"""
        subcircuit = self.get_component(reference)
        if '_SUBCKT' in subcircuit.attributes:  # Optimization: if it was already stored, return it
            return subcircuit.attributes['_SUBCKT']
        raise AttributeError(f"An associated subcircuit was not found for {reference}")

    def get_parameter(self, param: str) -> str:
        # docstring inherited from BaseEditor

        tag, match = self._get_param_named(param)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in QSCH file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        # docstring inherited from BaseEditor
        tag, match = self._get_param_named(param)
        if match:
            _logger.debug(f"Parameter {param} found in QSCH file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            text: str = tag.get_attr(QSCH_TEXT_STR_ATTR)
            start, stop = match.span("value")
            start += len(QSCH_TEXT_INSTR_QUALIFIER)
            stop += len(QSCH_TEXT_INSTR_QUALIFIER)
            text = text[:start] + value_str + text[stop:]
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

    def _get_component_symbol(self, reference: str) -> Tuple["BaseSchematic", str, QschTag]:
        sub_circuit, ref = self._get_parent(reference)
        if ref not in sub_circuit.components:
            _logger.error(f"Component {ref} not found")
            raise ComponentNotFoundError(f"Component {ref} not found in Schematic file")

        component = sub_circuit.components[ref]
        comp_tag: QschTag = component.attributes['tag']
        symbol: QschTag = comp_tag.get_items('symbol')[0]
        return sub_circuit, ref, symbol

    def set_component_value(self, reference: str, value: Union[str, int, float]) -> None:
        # docstring inherited from BaseEditor
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        if isinstance(value, str):
            value_str = value
        else:
            value_str = format_eng(value)
        self.set_element_model(reference, value_str)

    def set_element_model(self, device: str, model: str) -> None:
        # docstring inherited from BaseEditor
        sub_circuit, ref, symbol = self._get_component_symbol(device)
        texts = symbol.get_items('text')
        assert texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR) == ref
        texts[QSCH_SYMBOL_TEXT_VALUE].set_attr(QSCH_TEXT_STR_ATTR, model)
        sub_circuit.components[ref].attributes['value'] = model
        _logger.info(f"Component {device} updated to {model}")
        sub_circuit.updated = True

    def get_component_value(self, element: str) -> str:
        # docstring inherited from BaseEditor
        component = self.get_component(element)
        if "value" not in component.attributes:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return component.attributes["value"]

    def get_component_parameters(self, element: str) -> dict:
        """
        Returns the parameters of the component in a dictionary. Since QSpice stores attributes by their order of
        appearance on the QSCH file, some parameters may not be found if they are not in the standard format.
        If a line contains a parameter definition that is on the standard format, it will be parsed and stored in the
        dictionary. The key of the dictionary is the line number where the parameter was found.

        :param element: The reference of the component
        :type element: str
        :return: A dictionary with the parameters of the component
        :rtype: dict
        """
        _, _, symbol = self._get_component_symbol(element)
        texts = symbol.get_items('text')
        parameters = {}
        param_regex = re.compile(PARAM_REGEX(r'\w+'), re.IGNORECASE)
        for i in range(2, len(texts)):
            text = texts[i].get_attr(QSCH_TEXT_STR_ATTR)
            matches = param_regex.finditer(text)
            for match in matches:
                parameters[match.group('name')] = match.group('value')
            else:
                parameters[i] = text

        return parameters

    def set_component_parameters(self, element: str, **kwargs) -> None:
        """
        Sets the parameters of the component. If key parameters that are integers, they represent the line number
        where the parameter was found. If the key is a string, it represents the parameter name. If the parameter name
        already exists, it will be replaced. If not found, it will be added as a new text line.
        """
        sub_circuit, ref, symbol = self._get_component_symbol(element)
        texts = symbol.get_items('text')

        for key, value in kwargs.items():
            if isinstance(key, int):
                if key < 2 or key > len(texts):
                    raise ValueError(f"Invalid line number {key} for component {element}")
                if key == len(texts):
                    x, y = 0, 0  # TODO: Find a way to get the position of the last text
                    tag, _ = QschTag.parse(
                        f'«text ({x},{y}) 1 7 0 0x1000000 -1 -1 "{value}"»'
                    )
                    symbol.items.append(tag)

                else:
                    texts[key].set_attr(QSCH_TEXT_STR_ATTR, value)
                sub_circuit.updated = True
            else:
                found = False
                search_expression = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
                for text in texts[QSCH_SYMBOL_TEXT_VALUE:]:
                    text_value = text.get_attr(QSCH_TEXT_STR_ATTR)

                    for match in search_expression.finditer(text_value):
                        if match.group("name") == key:
                            start, stop = match.span("value")
                            text_value = text_value[:start] + value + text_value[stop:]
                            text.set_attr(QSCH_TEXT_STR_ATTR, text_value)
                            sub_circuit.updated = True
                            found = True
                            break
                        if found:
                            break
                if not found:
                    x, y = 0, 0  # TODO: Find a way to get the position of the last text
                    new_tag, _ = QschTag.parse(
                        f'«text ({x},{y}) 0.5 0 0 0x1000000 -1 -1 "{key}={value}"»'
                    )
                    # Inserting the new tag just after the last text and the first pin
                    last_text = 0
                    for i, tag in enumerate(symbol.items):
                        if tag.tag == 'pin':
                            last_text = i
                            break
                        elif tag.tag == 'text':
                            last_text = i + 1  # The new text should be inserted after the last text
                    if 0 <= last_text < len(symbol.items):
                        symbol.items.insert(last_text, new_tag)
                    else:
                        symbol.items.append(new_tag)
                    sub_circuit.updated = True

    def get_component_position(self, reference: str) -> Tuple[Point, ERotation]:
        # docstring inherited from BaseSchematic
        component = self.get_component(reference)
        return component.position, component.rotation

    def set_component_position(self, reference: str,
                               position: Union[Point, tuple],
                               rotation: Union[ERotation, int],
                               mirror: bool = False,
                               ) -> None:
        # docstring inherited from BaseSchematic
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
        # docstring inherited from BaseEditor
        if prefixes == '*':
            return list(self.components.keys())
        return [k for k in self.components.keys() if k[0] in prefixes]

    def remove_component(self, designator: str):
        # docstring inherited from BaseEditor
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
        # docstring inherited from BaseEditor
        instruction = instruction.strip()  # Clean any end of line terminators
        command = instruction.split()[0].upper()

        if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            for text_tag in self.schematic.get_items('text'):
                if text_tag.get_attr(QSCH_TEXT_COMMENT) == 1:  # if it is a comment, we ignore it
                    continue
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
        # docstring inherited from BaseEditor
        for text_tag in self.schematic.get_items('text'):
            text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            if instruction in text:
                self.schematic.items.remove(text_tag)
                _logger.info(f'Instruction "{instruction}" removed')
                return  # Job done, can exit this method

        msg = f'Instruction "{instruction}" not found'
        _logger.error(msg)

    def remove_Xinstruction(self, search_pattern: str) -> None:
        # docstring inherited from BaseEditor
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
        # docstring inherited from BaseSchematic
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

            for line in self.lines:
                line_tag, _ = QschTag.parse('«line (2000,1300) (3150,-100) 0 2 0xff0000 -1 -1»')
                line_tag.set_attr(QSCH_LINE_POS1, (line.V1.X, line.V1.Y))
                line_tag.set_attr(QSCH_LINE_POS2, (line.V2.X, line.V2.Y))
                # TODO: Implement the style to width, type and color
                # line_width = 0  # Default
                # line_type = 0  # Default
                # color = 0xff0000  # Default : Blue Color
                # line_width, line_type, color = line.style.split(' ')
                # line_tag.set_attr(QSCH_LINE_WIDTH, line_width)
                # line_tag.set_attr(QSCH_LINE_TYPE, line_type)
                # line_tag.set_attr(QSCH_LINE_COLOR, color)
                self.schematic.items.append(line_tag)

            for shape in self.shapes:
                # TODO: Implement the line type and width conversion from LTSpice to QSpice.
                if shape.name == "RECTANGLE" or shape.name == "rect":
                    shape_tag, _ = QschTag.parse('«rect (1850,1550) (3650,-400) 0 0 2 0xff0000 0x1000000 -1 0 -1»')
                    shape_tag.set_attr(QSCH_RECT_POS1, (shape.points[0].X, shape.points[0].Y))
                    shape_tag.set_attr(QSCH_RECT_POS2, (shape.points[1].X, shape.points[1].Y))
                    # shape_tag.set_attr(QSCH_RECT_LINE_TYPE, shape.line_style.pattern)
                    # shape_tag.set_attr(QSCH_RECT_LINE_WIDTH, shape.line_style.width)
                    # shape_tag.set_attr(QSCH_RECT_LINE_COLOR, shape.line_style.color)
                elif shape.name == "CIRCLE" or shape.name == "ellipse":
                    shape_tag, _ = QschTag.parse('«ellipse (2100,1150) (2650,150) 0 0 2 0xff0000 0x1000000 -1 -1»')
                    shape_tag.set_attr(QSCH_ELLIPSE_POS1, (shape.points[0].X, shape.points[0].Y))
                    shape_tag.set_attr(QSCH_ELLIPSE_POS2, (shape.points[1].X, shape.points[1].Y))
                    # shape_tag.set_attr(QSCH_ELLIPSE_LINE_COLOR, shape.line_style.color)
                    # shape_tag.set_attr(QSCH_ELLIPSE_FILL_COLOR, shape.fill)
                elif shape.name == "ARC" or shape.name == "arc3p":
                    shape_tag, _ = QschTag.parse('«arc3p (2700,300) (2250,1200) (2500,800) 0 2 0xff0000 -1 -1»')
                    # TODO: Implement the ARC shape correctly.
                    # In LTSpice the First two points defines the bounding box of the arc and the following
                    # two points define the start and end of the arc.
                    # QSpice uses the first two points to define the start and end of the arc and the third point
                    # to define the curvature of the arc.
                    if shape.name == "ARC":
                        assert len(shape.points) == 4, "Invalid LTSpice shape"
                        center_x = int((shape.points[0].X + shape.points[1].X) / 2)
                        center_y = int((shape.points[0].Y + shape.points[1].Y) / 2)
                        start_angle = math.atan2(shape.points[2].Y - center_y, shape.points[2].X - center_x)
                        end_angle = math.atan2(shape.points[3].Y - center_y, shape.points[3].X - center_x)
                        ellipse_width = abs(shape.points[1].X - shape.points[0].X)
                        ellipse_height = abs(shape.points[1].Y - shape.points[0].Y)
                        start_point_x = int(center_x + ellipse_width / 2 * math.cos(start_angle))
                        start_point_y = int(center_y + ellipse_height / 2 * math.sin(start_angle))
                        end_point_x = int(center_x + ellipse_width / 2 * math.cos(end_angle))
                        end_point_y = int(center_y + ellipse_height / 2 * math.sin(end_angle))
                        shape_tag.set_attr(QSCH_ARC3P_POS1, (start_point_x, start_point_y))
                        shape_tag.set_attr(QSCH_ARC3P_POS2, (end_point_x, end_point_y))
                        shape_tag.set_attr(QSCH_ARC3P_POS3, (center_x, center_y))
                    else:
                        shape_tag.set_attr(QSCH_ARC3P_POS1, (shape.points[0].X, shape.points[0].Y))
                        shape_tag.set_attr(QSCH_ARC3P_POS2, (shape.points[1].X, shape.points[1].Y))
                        shape_tag.set_attr(QSCH_ARC3P_POS3, (shape.points[2].X, shape.points[2].Y))
                        # shape_tag.set_attr(QSCH_ARC3P_LINE_COLOR, shape.line_style.color)
                else:
                    print(f"Invalid shape {shape.name}. Being ignored. Ask Developper to implement this")

                self.schematic.items.append(shape_tag)

            for text in self.directives:
                text_tag, _ = QschTag.parse('«text (0,0) 1 7 0 0x1000000 -1 -1 "text"»')
                text_tag.set_attr(QSCH_TEXT_STR_ATTR, QSCH_TEXT_INSTR_QUALIFIER + text.text)
                text_tag.set_attr(QSCH_TEXT_POS, (text.coord.X, text.coord.Y))
                self.schematic.items.append(text_tag)
