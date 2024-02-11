#!/usr/bin/env python
# coding=utf-8
import abc
import dataclasses
import enum
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        base_editor.py
# Purpose:     Abstract class that defines the protocol for the editors
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------


from typing import List
from collections import OrderedDict
import logging
from .base_editor import BaseEditor, Component

_logger = logging.getLogger("spicelib.BaseSchematic")


class ERotation(enum.Enum):
    """Component Rotation Enum"""
    R0 = "0 Rotation"
    R45 = "45 Rotation"
    R90 = "90 Rotation"
    R135 = "135 Rotation"
    R180 = "180 Rotation"
    R225 = "225 Rotation"
    R270 = "270 Rotation"
    R315 = "315 Rotation"
    M0 = "Mirror 0 Rotation"
    M45 = "Mirror 45 Rotation"
    M90 = "Mirror 90 Rotation"
    M135 = "Mirror 135 Rotation"
    M180 = "Mirror 180 Rotation"
    M225 = "Mirror 225 Rotation"
    M270 = "Mirror 270 Rotation"
    M315 = "Mirror 315 Rotation"


class HorAlign(enum.Enum):
    """Horizontal Alignment Enum"""
    LEFT = "Left"
    RIGHT = "Right"
    CENTER = "Center"


class VerAlign(enum.Enum):
    """Vertical Alignment Enum"""
    TOP = "Top"
    CENTER = "Center"
    BOTTOM = "Bottom"


class TextTypeEnum(enum.IntEnum):
    """Text Type Enum"""
    NULL = enum.auto()
    COMMENT = enum.auto()
    DIRECTIVE = enum.auto()
    LABEL = enum.auto()
    ATTRIBUTE = enum.auto()


@dataclasses.dataclass
class Point:
    """X, Y coordinates"""
    X: int
    Y: int


@dataclasses.dataclass
class Line:
    """X1, Y1, X2, Y2 coordinates"""
    V1: Point
    V2: Point
    net: str = ""

    def touches(self, point: Point) -> bool:
        """Returns True if the line passes through the given point"""
        if self.V1.X == self.V2.X:
            if self.V1.X == point.X:
                if min(self.V1.Y, self.V2.Y) <= point.Y <= max(self.V1.Y, self.V2.Y):
                    return True
        elif self.V1.Y == self.V2.Y:
            if self.V1.Y == point.Y:
                if min(self.V1.X, self.V2.X) <= point.X <= max(self.V1.X, self.V2.X):
                    return True
        else:
            # The time saving tricks are over, the line is oblique, so, we have to do the math
            # The line is defined by the equation y = m*x + b
            # where m is the slope and b is the y intercept
            m = (self.V2.Y - self.V1.Y) / (self.V2.X - self.V1.X)
            b = self.V1.Y - m * self.V1.X
            # Now we can calculate the Y value for the given X
            y = m * point.X + b
            # If the Y value is the same as the point Y, then the line passes through the point
            if y == point.Y:
                # Now we have to check if the point is within the line segment
                if min(self.V1.X, self.V2.X) <= point.X <= max(self.V1.X, self.V2.X):
                    return True
        return False

    def intercepts(self, line: 'Line') -> bool:
        """Returns True if the line intercepts the given line.
        The intercepts is calculated by checking if the line touches any of the line vertices
        """
        # We have to check if the line touches any of the vertices of the given line
        if self.touches(line.V1) or self.touches(line.V2):
            return True
        # We also have to check if the given line touches any of the vertices of this line
        if line.touches(self.V1) or line.touches(self.V2):
            return True
        return False


@dataclasses.dataclass
class Text:
    """Text object"""
    coord: Point
    text: str
    size: int = 1
    type: TextTypeEnum = TextTypeEnum.NULL
    textAlignment: HorAlign = HorAlign.LEFT
    verticalAlignment: VerAlign = VerAlign.CENTER


class SchematicComponent(Component):
    """Hols component information"""

    def __init__(self):
        super().__init__()
        self.position: Point = Point(0, 0)
        self.rotation: ERotation = ERotation.R0
        self.symbol = None


class BaseSchematic(BaseEditor):
    """
    This defines the primitives (protocol) to be used for both SpiceEditor and AscEditor
    classes.
    """

    def __init__(self):
        self._components: OrderedDict[str, SchematicComponent] = OrderedDict()
        self._wires: List[Line] = []
        self._labels: List[Text] = []
        self._directives: List[Text] = []

    def reset_netlist(self) -> None:
        """Resets the netlist to the original state"""
        self._components.clear()
        self._wires.clear()
        self._labels.clear()
        self._directives.clear()

    @abc.abstractmethod
    def get_component(self, reference: str) -> SchematicComponent:
        """Returns the SchematicComponent object representing the given reference in the schematic file"""
        ...

    @abc.abstractmethod
    def get_component_position(self, reference: str) -> (Point, ERotation):
        """Returns the position of the component"""
        ...

    @abc.abstractmethod
    def set_component_position(self, reference: str, position: Point, rotation: ERotation) -> None:
        """Sets the position of the component"""
        ...
