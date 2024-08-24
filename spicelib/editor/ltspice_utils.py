# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        ltspice_utils.py
# Purpose:     Utility functions for LTSpice files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     28-03-2024
# Licence:     refer to the LICENSE file
#
# -------------------------------------------------------------------------------

import re

from .base_schematic import ERotation, Text, HorAlign, VerAlign

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2024, Fribourg Switzerland"


# Regular expressions
TEXT_REGEX = re.compile(
    r"TEXT (-?\d+)\s+(-?\d+)\s+V?(Left|Right|Top|Bottom|Center|Invisible)\s(\d+)\s*(?P<type>[!;])(?P<text>.*)",
    re.IGNORECASE
)

TEXT_REGEX_X = 1
TEXT_REGEX_Y = 2
TEXT_REGEX_ALIGN = 3
TEXT_REGEX_SIZE = 4
TEXT_REGEX_TYPE = 5
TEXT_REGEX_TEXT = 6
END_LINE_TERM = "\n"
ASC_ROTATION_DICT = {
    'R0': ERotation.R0,
    'R90': ERotation.R90,
    'R180': ERotation.R180,
    'R270': ERotation.R270,
    'M0': ERotation.M0,
    'M90': ERotation.M90,
    'M180': ERotation.M180,
    'M270': ERotation.M270,
}
ASC_INV_ROTATION_DICT = {val: key for key, val in ASC_ROTATION_DICT.items()}
LT_ATTRIBUTE_NUMBERS = {
    'Prefix': 0,
    'Type': 1,
    'Value': 3,
    'Value2': 123,
    'SpiceModel': 38,
    'ModelFile': 'X',
    'Def_Sub': 'X',
    'SpiceLine': 39,
    'SpiceLine2': 40,
}
LT_ATTRIBUTE_NUMBERS_INV = {val: key for key, val in LT_ATTRIBUTE_NUMBERS.items()}
# not used right now, LTSpice does not seem to support it
WEIGHT_CONVERSION_TABLE = ('Thin', 'Normal', 'Thick')


def asc_text_align_set(text: Text, alignment: str):
    """Sets the alignment of the text in the ASC format"""
    # Default
    text.textAlignment = HorAlign.CENTER
    text.verticalAlignment = VerAlign.CENTER
    if alignment == 'Left' or alignment == 'VLeft':
        text.textAlignment = HorAlign.LEFT
    elif alignment == 'Center' or alignment == 'VCenter':
        pass
    elif alignment == 'Right' or alignment == 'VRight':
        text.textAlignment = HorAlign.RIGHT
    elif alignment == 'Top' or alignment == 'VTop':
        text.verticalAlignment = VerAlign.TOP
    elif alignment == 'Bottom' or alignment == 'VBottom':
        text.verticalAlignment = VerAlign.BOTTOM
    elif alignment == 'Invisible' or alignment == 'VInvisible':
        text.visible = False
    else:
        raise ValueError(f"Invalid alignment {alignment}")

    if alignment.startswith('V'):
        text.angle = ERotation.R90
    else:
        text.angle = ERotation.R0
    return text


def asc_text_align_get(text: Text) -> str:
    """Returns the alignment of the text in the ASC format"""
    if not text.visible:
        ans = 'Invisible'
    else:
        if text.verticalAlignment == VerAlign.CENTER:
            if text.textAlignment == HorAlign.RIGHT:
                ans = 'Right'
            elif text.textAlignment == HorAlign.CENTER:
                ans = 'Center'
            else:
                ans = 'Left'
        else:
            if text.verticalAlignment == VerAlign.TOP:
                ans = 'Top'
            elif text.verticalAlignment == VerAlign.BOTTOM:
                ans = 'Bottom'
            else:            
                ans = 'Left'

    if text.angle == ERotation.R90:
        ans = 'V' + ans
    return ans
