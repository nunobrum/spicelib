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


from typing import List, Callable, Union
from collections import OrderedDict
import logging
from .base_editor import BaseEditor, Component, ComponentNotFoundError

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
    X: float
    Y: float


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
        self.components: OrderedDict[str, SchematicComponent] = OrderedDict()
        self.wires: List[Line] = []
        self.labels: List[Text] = []
        self.directives: List[Text] = []

    def reset_netlist(self, create_blank: bool = False) -> None:
        """Resets the netlist to the original state"""
        self.components.clear()
        self.wires.clear()
        self.labels.clear()
        self.directives.clear()

    def copy_from(self, editor: 'BaseSchematic') -> None:
        """Copies the contents of the given editor"""
        from copy import deepcopy
        self.components = deepcopy(editor.components)
        self.wires = deepcopy(editor.wires)
        self.labels = deepcopy(editor.labels)
        self.directives = deepcopy(editor.directives)

    def get_component(self, reference: str) -> SchematicComponent:
        """Returns the SchematicComponent object representing the given reference in the schematic file"""
        if reference not in self.components:
            _logger.error(f"Component {reference} not found")
            raise ComponentNotFoundError(f"Component {reference} not found in ASC file")
        return self.components[reference]

    def get_component_position(self, reference: str) -> (Point, ERotation):
        """Returns the position and rotation of the component"""
        comp = self.get_component(reference)
        return comp.position, comp.rotation

    def set_component_position(self, reference: str, position: Point, rotation: ERotation) -> None:
        """Sets the position of the component"""
        comp = self.get_component(reference)
        comp.position = position
        comp.rotation = rotation

    def add_component(self, component: SchematicComponent, **kwargs) -> None:
        if component.reference in self.components:
            # The component is already in the list, so we need to update it
            comp = self.components[component.reference]
        else:
            comp = SchematicComponent()
            comp.reference = component.reference
        self.components[component.reference] = comp

    def scale(self, offset_x, offset_y, scale_x, scale_y: float,
              round_fun: Callable[[float], Union[int, float]] = None) -> None:
        """Scales the schematic"""
        if round_fun is None:
            round_fun = int
        for comp in self.components.values():
            comp.position.X = round_fun(comp.position.X * scale_x + offset_x)
            comp.position.Y = round_fun(comp.position.Y * scale_y + offset_y)
        for wire in self.wires:
            wire.V1.X = round_fun(wire.V1.X * scale_x + offset_x)
            wire.V1.Y = round_fun(wire.V1.Y * scale_y + offset_y)
            wire.V2.X = round_fun(wire.V2.X * scale_x + offset_x)
            wire.V2.Y = round_fun(wire.V2.Y * scale_y + offset_y)
        for label in self.labels:
            label.coord.X = round_fun(label.coord.X * scale_x + offset_x)
            label.coord.Y = round_fun(label.coord.Y * scale_y + offset_y)
        for directive in self.directives:
            directive.coord.X = round_fun(directive.coord.X * scale_x + offset_x)
            directive.coord.Y = round_fun(directive.coord.Y * scale_y + offset_y)
