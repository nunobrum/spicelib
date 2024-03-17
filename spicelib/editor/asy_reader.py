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

from .base_schematic import Point, Text, TextTypeEnum, Line, Circle, Rectangle, Arc, HorAlign, ERotation, VerAlign
from .asc_editor import asc_text_align_set, TEXT_REGEX, LT_ATTRIBUTE_NUMBERS, LT_ATTRIBUTE_NUMBERS_INV, \
    WEIGHT_CONVERSION_TABLE

from .qsch_editor import QschTag

_logger = logging.getLogger("spicelib.AsyReader")
SCALE_X = 6.25
SCALE_Y = - 6.25


class AsyReader(object):
    """Symbol parser"""

    def __init__(self, asy_file: Union[Path, str]):
        super().__init__()
        self.version = 4
        self.symbol_type = None
        self.pins = []
        self.lines = []
        self.arcs = []
        self.circles = []
        self.rectangles = []
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
                    tokens = line.split(maxsplit=2)
                    if len(tokens) == 3:
                        tag, ref, text = tokens
                    elif len(tokens) == 2:
                        tag, ref = tokens
                        text = ""
                    else:
                        continue
                    text = text.strip()  # Gets rid of the \n terminator
                    self.attributes[ref] = text
                elif line.startswith("LINE"):
                    tag, weight, x1, y1, x2, y2 = line.split()
                    v1 = Point(int(x1), int(y1))
                    v2 = Point(int(x2), int(y2))
                    segment = Line(v1, v2, style=f"{{weight:{weight}}}")
                    self.lines.append(segment)
                elif line.startswith("CIRCLE"):
                    tag, weight, x1, y1, x2, y2 = line.split()
                    # In LTspice the circle is set using the top left and bottom right points of the rectangle that
                    # encloses the circle
                    x1 = int(x1)
                    x2 = int(x2)
                    y1 = int(y1)
                    y2 = int(y2)
                    # distance = (x2-x1)  # Always assuming a circle
                    # circle = Arc(Point((x1+x2)/2, (y1+y2)/2), radius=distance/2, start_angle=0, stop_angle=360,
                    #              style=f"{{style:1, weight:{weight}}}")
                    circle = Circle(Point(x1, y1), Point(x2, y2))
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
                elif line.startswith("ARC"):
                    tag, weight, x1, y1, x2, y2, x3, y3, x4, y4  = line.split()
                    x1 = int(x1)
                    x2 = int(x2)
                    x3 = int(x3)
                    x4 = int(x4)
                    y1 = int(y1)
                    y2 = int(y2)
                    y3 = int(y3)
                    y4 = int(y4)

                    center = Point((x1+x2)//2, (y1+y2)//2)
                    radius = abs(x2-x1)/2  # Using only the X axis. Assuming a circle not an elipse
                    start = Point((x3-center.X)/radius, (y3-center.Y)/radius)
                    stop = Point((x4-center.X)/radius, (y4-center.Y)/radius)
                    arc = Arc(center, radius=radius, start=start, stop=stop)
                    self.arcs.append(arc)
                elif line.startswith("RECTANGLE"):
                    tag, weight, x1, y1, x2, y2 = line.split()
                    x1 = int(x1)
                    x2 = int(x2)
                    y1 = int(y1)
                    y2 = int(y2)
                    rect = Rectangle(Point(x1, y1), Point(x2, y2))
                    self.rectangles.append(rect)
                else:
                    print("Primitive not supported for ASC file\n"
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
            x1 = int(line.V1.X * SCALE_X)
            y1 = int(line.V1.Y * SCALE_Y)
            x2 = int(line.V2.X * SCALE_X)
            y2 = int(line.V2.Y * SCALE_Y)
            segment, _ = QschTag.parse(
                f"«line ({x1},{y1}) ({x2},{y2}) 0 0 0x1000000 -1 -1»")
            symbol.items.append(segment)

        for circle in self.circles:
            # x1 = int((arc.center.X - arc.radius) * SCALE_X)
            # y1 = int((arc.center.Y - arc.radius) * SCALE_Y)
            # x2 = int((arc.center.X + arc.radius) * SCALE_X)
            # y2 = int((arc.center.Y + arc.radius) * SCALE_Y)
            x1 = int(circle.V1.X * SCALE_X)
            y1 = int(circle.V1.Y * SCALE_Y)
            x2 = int(circle.V2.X * SCALE_X)
            y2 = int(circle.V2.Y * SCALE_Y)
            elipse_tag, _ = QschTag.parse(
                f"«ellipse ({x1},{y1}) ({x2},{y2}) 0 0 0 0x1000000 0x1000000 -1 -1»"
            )
            symbol.items.append(elipse_tag)

        for rectangle in self.rectangles:
            x1 = int(rectangle.V1.X * SCALE_X)
            y1 = int(rectangle.V1.Y * SCALE_Y)
            x2 = int(rectangle.V2.X * SCALE_X)
            y2 = int(rectangle.V2.Y * SCALE_Y)
            rectangle_tag, _ = QschTag.parse(
                f"«rect ({x1},{y1}) ({x2},{y2}) 0 0 2 0x4000000 0x1000000 -1 0 -1»"
            )
            symbol.items.append(rectangle_tag)

        for arc in self.arcs:
            cx = int(arc.center.X * SCALE_X)
            cy = int(arc.center.Y * SCALE_Y)
            x1 = int((arc.center.X + arc.start.X * arc.radius) * SCALE_X)
            y1 = int((arc.center.Y + arc.start.Y * arc.radius) * SCALE_Y)
            x2 = int((arc.center.X + arc.stop.X * arc.radius) * SCALE_X)
            y2 = int((arc.center.Y + arc.stop.Y * arc.radius) * SCALE_Y)

            elipse_tag, _ = QschTag.parse(
                f"«arc3p ({x1},{y1}) ({x2},{y2}) ({cx},{cy}) 0 2 0xff0000 -1 -1»"
            )
            symbol.items.append(elipse_tag)
        for i, attr in enumerate(self.windows):
            coord = attr.coord
            x = coord.X * SCALE_X
            y = coord.Y * SCALE_Y
            text, _ = QschTag.parse(f'«text ({x :.0f},{y :.0f})'
                                    f' 1 7 0 0x1000000 -1 -1 "{args[i]}"»')
            symbol.items.append(text)

        for pin in self.pins:
            coord = pin.coord
            attr_dict = {}
            for pair in pin.text.split(";"):
                if '=' in pair:
                    k, v = pair.split('=')
                    attr_dict[k] = v

            pin_tag, _ = QschTag.parse(f'«pin ({coord.X * SCALE_X:.0f},{coord.Y * SCALE_Y:.0f}) (0,0)'
                                       f' 1 0 0 0x1000000 -1 "{attr_dict["PinName"]}"»')
            symbol.items.append(pin_tag)

        return symbol
