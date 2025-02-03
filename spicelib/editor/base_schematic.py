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
# Name:        base_schematic.py
# Purpose:     Base classes for schematic editors
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------


import dataclasses
import enum
from typing import List, Callable, Union, Tuple
from collections import OrderedDict
import logging
from .base_editor import BaseEditor, Component, ComponentNotFoundError, SUBCKT_DIVIDER

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

_logger = logging.getLogger("spicelib.BaseSchematic")


class ERotation(enum.IntEnum):
    """Component Rotation Enum"""
    R0 = 0  # 0 Rotation
    R45 = 45  # 45 Rotation
    R90 = 90  # 90 Rotation
    R135 = 135  # 135 Rotation
    R180 = 180  # 180 Rotation
    R225 = 225  # 225 Rotation
    R270 = 270  # 270 Rotation
    R315 = 315  # 315 Rotation
    M0 = 360 + 0  # Mirror 0 Rotation
    M45 = 360 + 45  # Mirror 45 Rotation
    M90 = 360 + 90  # Mirror 90 Rotation
    M135 = 360 + 135  # Mirror 135 Rotation
    M180 = 360 + 180  # Mirror 180 Rotation
    M225 = 360 + 225  # Mirror 225 Rotation
    M270 = 360 + 270  # Mirror 270 Rotation
    M315 = 360 + 315  # Mirror 315 Rotation

    def __str__(self):
        if self.value == 0:
            return "0 Rotation"
        elif self.value == 45:
            return "45 Rotation"
        elif self.value == 90:
            return "90 Rotation"
        elif self.value == 135:
            return "135 Rotation"
        elif self.value == 180:
            return "180 Rotation"
        elif self.value == 225:
            return "225 Rotation"
        elif self.value == 270:
            return "270 Rotation"
        elif self.value == 315:
            return "315 Rotation"
        elif self.value == 360 + 0:
            return "Mirror 0 Rotation"
        elif self.value == 360 + 45:
            return "Mirror 45 Rotation"
        elif self.value == 360 + 90:
            return "Mirror 90 Rotation"
        elif self.value == 360 + 135:
            return "Mirror 135 Rotation"
        elif self.value == 360 + 180:
            return "Mirror 180 Rotation"
        elif self.value == 360 + 225:
            return "Mirror 225 Rotation"
        elif self.value == 360 + 270:
            return "Mirror 270 Rotation"
        elif self.value == 360 + 315:
            return "Mirror 315 Rotation"

    # def mirror_y_axis(self):
    #     if self == ERotation.R0:
    #         return ERotation.M180
    #     elif self == ERotation.R90:
    #         return ERotation.M270
    #     elif self == ERotation.R180:
    #         return ERotation.M0
    #     elif self == ERotation.R270:
    #         return ERotation.M90
    #     elif self == ERotation.M0:
    #         return ERotation.R180
    #     elif self == ERotation.M90:
    #         return ERotation.R270
    #     elif self == ERotation.M180:
    #         return ERotation.R0
    #     elif self == ERotation.M270:
    #         return ERotation.R90
    #     else:
    #         return self
    #
    # def mirror_x_axis(self):
    #     return ERotation((((self.value + 180) % 360) + 360) % 720)

    def __add__(self, rotation: 'ERotation'):
        return (self.value + rotation.value) % 360


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
    PIN = enum.auto()  # pin label


class LineStyle:
    """Line style : width, color and pattern (dashed, dotted, etc...) """
    def __init__(self, width: str = "", color: str = "", pattern: str = ""):
        self.width: str = width
        self.color: str = color
        self.pattern: str = pattern


class Point:
    """X, Y coordinates"""
    def __init__(self, X: float, Y: float):
        self.X = X
        self.Y = Y


class Line:
    """X1, Y1, X2, Y2 coordinates"""
    def __init__(self, v1: Point, v2: Point, style: LineStyle = None, net: str = ""):
        self.V1 = v1
        self.V2 = v2
        if style is None:
            self.style = LineStyle()
        else:
            self.style = style
        self.net = net

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


class Shape:
    """Polygon object. The shape is defined by a list of points. It can define a closed or open shape.
    The closed shape is defined by the first and last points being the same. In this case, it can have a fill.
    It is used to define polygons, arcs, circles or more complex shapes like the ones found in QSPICE"""
    def __init__(self, name: str, points: List[Point], line_style: LineStyle = None, fill: str = ""):
        self.name = name
        self.points = points
        if line_style is None:
            self.line_style = LineStyle()
        else:
            self.line_style = line_style
        self.fill = fill

# Rectangle = Shape
# Rectangle is a special case of a Shape. Rectangle is defined by two points that define the diagonal
# of the rectangle.

# Circle = Shape  # Circle is a special case of a Shape. Circle is defined by the rectangle that encloses it.

# Arc = Shape
# Arc is a special case of a Shape. Since different tools have different ways of defining arcs, we will use
# # the Shape class to define them. We will only store the list of points that are provided by the tool.

#  TODO: The following code is commented out because it is not used in the current implementation. It is kept here for
# when we decode how ARCs are stored and we could use it to update them.
# @dataclasses.dataclass
# class Arc:
#     """Opting for a non-native representation of the arc as LTspice and Qspice have different
#     ways of storing Arc information. Start and Stop points are calculated as a fraction of the radius
#     for X and Y. This avoids having to deal with the calculation of sines and cosines and their inverse
#     into radians."""
#     center: Point
#     radius: float
#     start: Point = Point(0, 0)
#     stop: Point = Point(0, 0)
#     style: LineStyle = LineStyle()
#     # The Arcs are decorative, they don't have associated nets


@dataclasses.dataclass
class Text:
    """Text object"""
    coord: Point
    text: str
    size: int = 1
    type: TextTypeEnum = TextTypeEnum.NULL
    textAlignment: HorAlign = HorAlign.LEFT
    verticalAlignment: VerAlign = VerAlign.CENTER
    angle: ERotation = ERotation.R0
    visible: bool = True


@dataclasses.dataclass
class Port:
    text: Text
    direction: str


class SchematicComponent(Component):
    """Holds component information"""

    def __init__(self, parent, line):
        super().__init__(parent, line)
        self.position: Point = Point(0, 0)
        self.rotation: ERotation = ERotation.R0
        self.symbol = None

    def __str__(self):
        return f"{self.reference} {self.position.X} {self.position.Y} {self.rotation}"


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
        self.ports: List[Port] = []
        self.lines: List[Line] = []
        self.shapes: List[Shape] = []
        self.updated = False  # indicates if an edit was done and the file has to be written back to disk

    def reset_netlist(self, create_blank: bool = False) -> None:
        """Resets the netlist to the original state"""
        self.components.clear()
        self.wires.clear()
        self.labels.clear()
        self.directives.clear()
        self.lines.clear()
        self.shapes.clear()
        self.updated = False

    def copy_from(self, editor: 'BaseSchematic') -> None:
        """Clones the contents of the given editor"""
        from copy import deepcopy
        self.components = deepcopy(editor.components)
        self.wires = deepcopy(editor.wires)
        self.labels = deepcopy(editor.labels)
        self.directives = deepcopy(editor.directives)
        self.lines = deepcopy(editor.lines)
        self.shapes = deepcopy(editor.shapes)
        self.updated = True

    def _get_parent(self, reference) -> Tuple["BaseSchematic", str]:
        if SUBCKT_DIVIDER in reference:
            sub_ref, sub_comp = reference.split(SUBCKT_DIVIDER, 1)

            subckt = self.get_component(sub_ref)
            subcircuit = subckt.attributes['_SUBCKT']
            return subcircuit, sub_comp
        else:
            return self, reference

    def set_updated(self, reference):
        """:meta private:"""
        sub_circuit, _ = self._get_parent(reference)
        sub_circuit.updated = True

    def get_component(self, reference: str) -> SchematicComponent:
        """
        Returns the SchematicComponent object representing the given reference in the schematic file.

        :param reference: The reference of the component
        :return: The SchematicComponent object
        :raises ComponentNotFoundError: If the component is not found.
        """
        sub_circuit, ref = self._get_parent(reference)

        if sub_circuit != self:  # The component is in a subcircuit
            return sub_circuit.get_component(ref)
        else:
            if ref not in sub_circuit.components:
                _logger.error(f"Component {reference} not found")
                raise ComponentNotFoundError(f"Component {reference} not found in Schematic file")
            return sub_circuit.components[ref]

    def get_component_position(self, reference: str) -> Tuple[Point, ERotation]:
        """Returns the position and rotation of the component"""
        comp = self.get_component(reference)
        return comp.position, comp.rotation

    def set_component_position(self, reference: str, position: Point, rotation: ERotation) -> None:
        """Sets the position and rotation of the component.

        :param reference: The reference of the component
        :type reference: str
        :param position: The new position of the component
        :type position: Point
        :param rotation: The new rotation of the component
        :type rotation: ERotation
        """
        comp = self.get_component(reference)
        comp.position = position
        comp.rotation = rotation
        self.set_updated(reference)

    def add_component(self, component: SchematicComponent, **kwargs) -> None:
        self.components[component.reference] = component
        component.parent = self
        if kwargs:
            # Update attributes
            component.attributes.update(kwargs)
        self.updated = True

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
        for port in self.ports:
            port.text.coord.X = round_fun(port.text.coord.X * scale_x + offset_x)
            port.text.coord.Y = round_fun(port.text.coord.Y * scale_y + offset_y)
        for line in self.lines:
            line.V1.X = round_fun(line.V1.X * scale_x + offset_x)
            line.V1.Y = round_fun(line.V1.Y * scale_y + offset_y)
            line.V2.X = round_fun(line.V2.X * scale_x + offset_x)
            line.V2.Y = round_fun(line.V2.Y * scale_y + offset_y)
        for shape in self.shapes:
            for point in shape.points:
                point.X = round_fun(point.X * scale_x + offset_x)
                point.Y = round_fun(point.Y * scale_y + offset_y)
        self.updated = True
