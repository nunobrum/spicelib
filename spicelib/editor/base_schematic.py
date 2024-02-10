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
from .base_editor import BaseEditor

_logger = logging.getLogger("spicelib.BaseSchematic")


class ERotation(enum.Enum):
    """Component Rotation Enum"""
    R0 = "0 Rotation"
    R90 = "90 Rotation"
    R180 = "180 Rotation"
    R270 = "270 Rotation"
    M0 = "Mirror 0 Rotation"
    M90 = "Mirror 90 Rotation"
    M180 = "Mirror 180 Rotation"
    M270 = "Mirror 270 Rotation"


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


@dataclasses.dataclass
class Text:
    """Text object"""
    coord: Point
    text: str
    size: int = 1
    type: TextTypeEnum = TextTypeEnum.NULL
    textAlignment: HorAlign = HorAlign.LEFT
    verticalAlignment: VerAlign = VerAlign.CENTER


class SchematicComponent(object):
    """Hols component information"""

    def __init__(self):
        self.position: Point = Point(0, 0)
        self.rotation: ERotation = ERotation.R0
        self.reference = ""
        self.attributes = OrderedDict()
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
