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
# Purpose:     Class to parse and then translate LTSpice symbol files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Union

from .base_schematic import Point, Text, TextTypeEnum, Line, Shape, HorAlign, ERotation, VerAlign
from .ltspice_utils import asc_text_align_set
from ..utils.detect_encoding import detect_encoding, EncodingDetectError
import re
from .qsch_editor import QschTag

_logger = logging.getLogger("spicelib.AsyReader")
SCALE_X = 6.25
SCALE_Y = - 6.25


class AsyReader(object):
    """Symbol parser"""

    def __init__(self, asy_file: Union[Path, str], encoding='autodetect'):
        super().__init__()
        self.version = 4
        self.symbol_type = None
        self.pins = []
        self.lines = []
        self.shapes = []
        self.attributes = OrderedDict()
        self._asy_file_path = Path(asy_file)
        self.windows = []
        pin = None
        if not self._asy_file_path.exists():
            raise FileNotFoundError(f"File {asy_file} not found")
        # determine encoding
        if encoding == 'autodetect':
            try:
                self.encoding = detect_encoding(self._asy_file_path, r'^VERSION ', re_flags=re.IGNORECASE)  # Normally the file will start with 'VERSION '
            except EncodingDetectError as err:
                raise err
        else:
            self.encoding = encoding
            
        with open(self._asy_file_path, 'r', encoding=self.encoding) as asc_file:
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
                    # make sure prefix is uppercase, as this is used in a lot of places
                    if ref.upper() == "PREFIX":
                        text = text.upper()
                    self.attributes[ref] = text
                elif line.startswith("Version"):
                    tag, version = line.split()
                    assert version in ["4", "4.0", "4.1"], f"Unsupported version : {version}"
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
                
                # the following is identical to the code in asc_reader.py. If you modify it, do so in both places.
                elif line.startswith("LINE") or line.startswith("RECTANGLE") or line.startswith("CIRCLE"):
                    # format: LINE|RECTANGLE|CIRCLE Normal, x1, y1, x2, y2, [line_style]
                    # Maybe support something else than 'Normal', but LTSpice does not seem to do so.
                    line_elements = line.split()
                    assert len(line_elements) in (6, 7), "Syntax Error, line badly badly formatted"
                    x1 = int(line_elements[2])
                    y1 = int(line_elements[3])
                    x2 = int(line_elements[4])
                    y2 = int(line_elements[5])
                    if line.startswith("LINE"):
                        line = Line(Point(x1, y1), Point(x2, y2))
                        if len(line_elements) == 7:
                            line.style.pattern = line_elements[6]
                        self.lines.append(line)
                    if line_elements[0] in ("RECTANGLE", "CIRCLE"):
                        shape = Shape(line_elements[0], [Point(x1, y1), Point(x2, y2)])
                        if len(line_elements) == 7:
                            shape.line_style.pattern = line_elements[6]
                        self.shapes.append(shape)
                        
                elif line.startswith("ARC"):
                    # I don't support editing yet, so why make it complicated
                    # format: ARC Normal, x1, y1, x2, y2, x3, y3, x4, y4 [line_style]
                    # Maybe support something else than 'Normal', but LTSpice does not seem to do so.
                    line_elements = line.split()
                    assert len(line_elements) in (10, 11), "Syntax Error, line badly formatted"
                    points = [Point(int(line_elements[i]), int(line_elements[i + 1])) for i in range(2, 9, 2)]
                    arc = Shape("ARC", points)
                    if len(line_elements) == 11:
                        arc.line_style.pattern = line_elements[10]
                    self.shapes.append(arc)

                elif line.startswith("TEXT "):
                    line_elements = line.split()
                    if len(line_elements) == 6:
                        x = int(line_elements[1])
                        y = int(line_elements[2])

                        text = Text(Point(x, y), text=line_elements[5], size=int(line_elements[4]),
                                    type=TextTypeEnum.COMMENT,
                                    textAlignment=HorAlign(line_elements[3]),
                                    )
                        self.windows.append(text)
                    else:
                        # Text in asy not supported however non-critical and not neccesary to crash the program.
                        _logger.warning(f"Cosmetic text in ASY format not supported, text skipped. ASY file: {self._asy_file_path}")
                else:
                    # In order to avoid crashing the program, 1) add the missing if statement above and
                    # 2) ontact the author to add support for the missing primitive.
                    raise NotImplementedError(f"Primitive not supported for ASY file \n" 
                                              f'"{line}"'
                                              f'in file: {self._asy_file_path}. Contact the author to add support.')
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

        for shape in self.shapes:
            if shape.name == "RECTANGLE":
                x1 = int(shape.points[0].X * SCALE_X)
                y1 = int(shape.points[0].Y * SCALE_Y)
                x2 = int(shape.points[1].X * SCALE_X)
                y2 = int(shape.points[1].Y * SCALE_Y)
                shape_tag, _ = QschTag.parse(
                    f"«rect ({x1},{y1}) ({x2},{y2}) 0 0 0 0x4000000 0x1000000 -1 0 -1»"
                )
            elif shape.name == "ARC":
                # translate from 4 points style of ltspice to 3 points style of qsch
                points = shape.points
                
                x1 = points[0].X
                x2 = points[1].X
                x3 = points[2].X
                x4 = points[3].X
                y1 = points[0].Y
                y2 = points[1].Y
                y3 = points[2].Y
                y4 = points[3].Y
                          
                center = Point((x1 + x2) // 2, (y1 + y2) // 2)
                radius = abs(x2 - x1) / 2  # Using only the X axis. Assuming a circle not an ellipse
                start = Point((x3 - center.X) / radius, (y3 - center.Y) / radius)
                stop = Point((x4 - center.X) / radius, (y4 - center.Y) / radius)
                # overwriting the points with the new ones
                x1 = int(center.X * SCALE_X)
                y1 = int(center.Y * SCALE_Y)
                x2 = int(start.X * SCALE_X)
                y2 = int(start.Y * SCALE_Y)
                x3 = int(stop.X * SCALE_X)
                y3 = int(stop.Y * SCALE_Y)
                shape_tag, _ = QschTag.parse(
                    f"«arc3p ({x1},{y1}) ({x2},{y2}) ({x3},{y3}) 0 0 0xff0000 -1 -1»"
                )
            elif shape.name == "CIRCLE" or shape.name == "ellipse":
                x1 = int(shape.points[0].X * SCALE_X)
                y1 = int(shape.points[0].Y * SCALE_Y)
                x2 = int(shape.points[1].X * SCALE_X)
                y2 = int(shape.points[1].Y * SCALE_Y)
                shape_tag, _ = QschTag.parse(
                    f"«ellipse ({x1},{y1}) ({x2},{y2}) 0 0 0 0x1000000 0x1000000 -1 -1»"
                )
            else:
                raise ValueError(f"Shape {shape.name} not supported")
            symbol.items.append(shape_tag)

        for i, attr in enumerate(self.windows):
            coord = attr.coord
            x = coord.X * SCALE_X
            y = coord.Y * SCALE_Y
            text, _ = QschTag.parse(f'«text ({x:.0f},{y:.0f})'
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

    def is_subcircuit(self):
        # Prefix is guaranteed to be uppercase
        return self.symbol_type == 'BLOCK' or self.attributes.get('Prefix') == 'X'

    def get_library(self) -> str:
        """Returns the library name of the model. If not found, returns None."""
        # Searching in this exact order
        suffixes = ('.lib', '.sub', '.cir', '.txt')  # must be lowercase here
        for attr in ('ModelFile', 'SpiceModel', 'SpiceLine', 'SpiceLine2', 'Def_Sub', 'Value', 'Value2'):
            if attr in self.attributes and (self.attributes[attr].lower().endswith(suffixes)):
                return self.attributes[attr]
        return self.attributes.get('SpiceModel')

    def get_model(self) -> str:
        """Returns the model name of the component. If not found, returns None."""
        # Searching in this exact order
        for attr in ('Value', 'SpiceModel', 'Value2', 'ModelFile', 'SpiceLine', 'SpiceLine2', 'Def_Sub', ):
            if attr in self.attributes:
                return self.attributes[attr]
        raise ValueError("No Value or Value2 attribute found")

    def get_value(self) -> Union[int, float, str]:
        """
        Returns the value of the component. If not found, returns None.
        If found it tries to convert the value to a number. If it fails, it returns the string.
        """
        value = self.get_model()
        try:
            ans = int(value)
        except ValueError:
            try:
                ans = float(value)
            except ValueError:
                ans = value.strip()  # Removes the leading trailing spaces
        return ans

    def get_schematic_file(self):
        """
        Returns the file name of the component, if it were a .asc file
        """        
        assert self._asy_file_path.suffix == '.asy', "File is not an asy file"
        assert self.symbol_type == 'BLOCK', "File is not a sub-circuit"
        return self._asy_file_path.with_suffix('.asc')
