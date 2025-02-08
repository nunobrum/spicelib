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
# -------------------------------------------------------------------------------
# Name:        international_support.py
# Purpose:     Pragmatic way to detect encoding.
#
# Author:      Nuno Brum (nuno.brum@gmail.com) with special thanks to Fugio Yokohama (yokohama.fujio@gmail.com)
#
# Created:     14-05-2022
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
International Support functions
Not using other known unicode detection libraries because we don't need something so complicated. LTSpice only supports
for the time being a reduced set of encodings.
"""
from pathlib import Path
from typing import Union
import re


class EncodingDetectError(Exception):
    """
    Exception raised when the encoding of a file cannot be detected
    """
    pass


def detect_encoding(file_path: Union[str, Path], expected_pattern: str = '', re_flags: re.RegexFlag = 0) -> str:
    """
    Simple strategy to detect file encoding.  If an expected_str is given the function will scan through the possible
    encodings and return a match.
    If an expected string is not given, it will use the second character is null, high chances are that this file has an
    'utf_16_le' encoding, otherwise it is assuming that it is 'utf-8'.
    :param file_path: path to the filename
    :type file_path: str
    :param expected_pattern: regular expression to match the first line of the file
    :type expected_pattern: str
    :param re_flags: flags to be used in the regular expression
    :type re_flags: int
    :return: detected encoding

    :rtype: str
    """
    for encoding in ('utf-8', 'utf-16', 'windows-1252', 'utf_16_le', 'cp1252', 'cp1250', 'shift_jis'):
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.read()
                f.seek(0)
        except UnicodeDecodeError:
            # This encoding didn't work, let's try again
            continue
        except UnicodeError:
            # This encoding didn't work, let's try again
            continue        
        else:
            if len(lines) == 0:
                # Empty file
                continue
            if expected_pattern:
                if not re.match(expected_pattern, lines, re_flags):
                    # File did not have the expected string
                    # Try again with a different encoding (This is unlikely to resolve the issue)
                    continue
            if encoding == 'utf-8' and lines[1] == '\x00':
                continue
            return encoding
    else:
        if expected_pattern:
            raise EncodingDetectError(f"Expected pattern \"{expected_pattern}\" not found in file:{file_path}")
        else:
            raise EncodingDetectError(f"Unable to detect encoding on log file: {file_path}")
