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
# Name:        editor_errors.py
# Purpose:     Custom exceptions for the Spice editor module
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# License:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import logging

_logger = logging.getLogger("spicelib.SpiceEditor")

class ComponentNotFoundError(Exception):
    """Component Not Found Error"""
    def __init__(self, reference):
        _logger.error(f'Component "{reference}" not found')
        super().__init__(f'Component "{reference}" not found')


class ValueNotFoundError(Exception):
    """Value Not Found Error"""
    def __init__(self, reference):
        _logger.error(f'Value not found on {reference}')
        super().__init__(f'Value not found on {reference}')


class ParameterNotFoundError(Exception):
    """ParameterNotFound Error"""
    def __init__(self, parameter, context):
        _logger.error(f'Parameter "{parameter}" not found in {context}')
        super().__init__(f'Parameter "{parameter}" not found in {context}')


class UnrecognizedSyntaxError(Exception):
    """Line doesn't match expected Spice syntax"""
    def __init__(self, line, regex):
        _logger.error(f"Line: \"{line}\" doesn't match regular expression \"{regex}\"")
        super().__init__(f"Line: \"{line}\" doesn't match regular expression \"{regex}\"")


class MissingExpectedClauseError(Exception):
    """Missing expected clause in Spice netlist"""
    def __init__(self, clause):
        _logger.error(f'Missing expected clause: {clause}')
        super().__init__(f'Missing expected clause: {clause}')
