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
# Name:        asy_reader.py
# Purpose:     Class to parse and then translate LTspice symbol files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Union

from .base_schematic import Point, Text, TextTypeEnum, Line, Arc, HorAlign, ERotation, VerAlign
from .asc_editor import asc_text_align_set, TEXT_REGEX, LT_ATTRIBUTE_NUMBERS, LT_ATTRIBUTE_NUMBERS_INV, \
    WEIGHT_CONVERSION_TABLE

from .qsch_editor import QschTag

_logger = logging.getLogger("spicelib.AsyReader")



class AsyReader(object):
    """Symbol parser"""

    def __init__(self, asy_file: Union[Path, str]):
        super().__init__()
        self.version = 4
        self.symbol_type = None
        self.pins = []
        self.lines = []
        self.circles = []
        self.attributes = OrderedDict()
        self._asy_file_path = Path(asy_file)
        self.windows = []
        pin = None
        if not self._asy_file_path.exists():
            raise FileNotFoundError(f"File {asy_file} not found")
        with open(self._asy_file_path, 'r') as asc_file:
            _logger.info(f"Parsing ASY file {self._asy_file_path}")
            for line in asc_file:
                if line.startswith("WINDOW"):
                    tag, num_ref, posX, posY, alignment, size = line.split()
                    coord = Point(int(posX), int(posY))
                    text = Text(coord=coord, text=num_ref, size=size, type=TextTypeEnum.ATTRIBUTE)
                    text = asc_text_align_set(text, alignment)
                    self.windows.append(text)
                elif line.startswith("SYMATTR"):
                    tag, ref, text = line.split(maxsplit=2)
                    text = text.strip()  # Gets rid of the \n terminator
                    self.attributes[ref] = text
                elif line.startswith("LINE"):
                    tag, weight, x1, y1, x2, y2 = line.split()
                    v1 = Point(int(x1), int(y1))
                    v2 = Point(int(x2), int(y2))
                    segment = Line(v1, v2, style=f"{{weight:{weight}}}")
                    self.lines.append(segment)
                elif line.startswith("CIRCLE"):
                    tag, weight, x1, y1, x2, y2, style = line.split()
                    # In LTspice the circle is set using the top left and bottom right points of the rectangle that
                    # encloses the circle
                    distance = ((x2-x1)**2 + (y1-y2)**2) ** 0.5  # Using pythagoras theorem
                    circle = Arc(Point((x1+x2)/2, (y1+y2)/2), radius=distance/2,
                                 style=f"{{style:{style}, weight:{weight}}}")
                    self.circles.append(circle)
                elif line.startswith("Version"):
                    tag, version = line.split()
                    assert version in ["4"], f"Unsupported version : {version}"
                    self.version = version
                elif line.startswith("SymbolType "):
                    self.symbol_type = line[len("SymbolType "):].strip()
                elif line.startswith("PINATTR"):
                    assert pin is not None, "A PIN was already created."
                    tag, attribute, value = line.split(' ', maxsplit=3)
                    value = value.strip()  # gets rid of the \n
                    pin.text += f"{attribute}={value};"
                elif line.startswith("PIN"):
                    if pin is not None:
                        self.pins.append(pin)
                    tag, x, y, justification, offset = line.split()
                    coord = Point(int(x), int(y))
                    angle = ERotation.R0

                    if justification == "NONE":
                        vertical_alignment = VerAlign.CENTER  # This signals that the pin is not visible
                        text_alignment = HorAlign.CENTER
                    else:
                        text_alignment = HorAlign.LEFT
                        vertical_alignment = VerAlign.BOTTOM
                        if justification.startswith("V"):  # Rotation to 90 degrees
                            angle = ERotation.R90
                            if justification == "VRIGHT":
                                text_alignment = HorAlign.RIGHT
                            elif justification == "VTOP":
                                text_alignment = VerAlign.TOP
                            # else other two cases are the default
                        else:
                            if justification == "TOP":
                                vertical_alignment = VerAlign.TOP
                            # elif justification == "BOTTOM":
                            #     vertical_alignment = VerAlign.BOTTOM (default)
                            elif justification == "RIGHT":
                                text_alignment = HorAlign.RIGHT
                            # else: justification == "LEFT" (default)

                    pin = Text(coord, "", type=TextTypeEnum.PIN, size=int(offset),
                               textAlignment=text_alignment, verticalAlignment=vertical_alignment, angle=angle)
                else:
                    raise NotImplementedError("Primitive not supported for ASC file\n"
                                              f'"{line}"')
            if pin is not None:
                self.pins.append(pin)

    def to_qsch(self, *args):
        """Create a QschTag representing a component symbol."""
        spice_prefix = self.attributes['Prefix']
        symbol = QschTag("symbol", spice_prefix[0])
        symbol.items.append(QschTag("type:", spice_prefix))
        symbol.items.append(QschTag("description:", self.attributes["Description"]))
        symbol.items.append(QschTag("shorted pins:", "false"))
        for line in self.lines:
            segment, _ = QschTag.parse(
                f"«line ({line.V1.X * 6.25:.0f},{line.V1.Y * -6.25:.0f}) "
                f"({line.V2.X * 6.25:.0f},{line.V2.Y * -6.25:.0f})"
                f" 0 0 0x1000000 -1 -1»")
            symbol.items.append(segment)
        for i, attr in enumerate(self.windows):
            coord = attr.coord
            text, _ = QschTag.parse(f'«text ({coord.X * 6.25:.0f},{coord.Y * -6.25:.0f})' 
                                    f' 1 7 0 0x1000000 -1 -1 "{args[i]}"»')
            symbol.items.append(text)
        for arc in self.circles:
            elipse_tag, _ = QschTag.parse("«ellipse (-130,130) (130,-130) 0 0 0 0x1000000 0x1000000 -1 -1»")
            symbol.items.append(elipse_tag)
        for pin in self.pins:
            coord = pin.coord
            attr_dict = {}
            for pair in pin.text.split(";"):
                if '=' in pair:
                    k, v = pair.split('=')
                    attr_dict[k] = v

            pin_tag, _ = QschTag.parse(f'«pin ({coord.X * 6.25:.0f},{coord.Y * -6.25:.0f}) (0,0)'
                                       f' 1 0 0 0x1000000 -1 "{attr_dict["PinName"]}"»')
            symbol.items.append(pin_tag)

        return symbol
