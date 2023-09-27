# -*- coding: utf-8 -*-

# Convenience direct imports
from .raw.raw_read import RawRead, SpiceReadException
from .raw.raw_write import RawWrite, Trace
from .editor.spice_editor import SpiceEditor, SpiceCircuit
from .editor.asc_editor import AscEditor
from .sim.sim_runner import SimRunner
from .simulators import LTspice, NGspice, Qspice, Xyce


def all_loggers():
    """
    Returns all the name strings used as logger identifiers.

    :return: A List of strings which contains all the logger's names used in this library.
    :rtype: list[str]
    """
    return [
        "spicelib.RunTask",
        "spicelib.LTSteps",
        "spicelib.SimClient",
        "spicelib.SimServer",
        "spicelib.ServerSimRunner",
        "spicelib.LTSteps",
        "spicelib.RawRead",
        "spicelib.LTSpiceSimulator",
        "spicelib.NGSpiceSimulator",
        "spicelib.QspiceSimulator",
        "spicelib.SimRunner",
        "spicelib.SimStepper",
        "spicelib.SpiceEditor",
        "spicelib.XYCESimulator",
        "spicelib.SimBatch",
        "spicelib.AscEditor",
    ]


def set_log_level(level):
    """
    Sets the logging level for all loggers used in the library.

    :param level: The logging level to be used, eg. logging.ERROR, logging.DEBUG, etc.
    :type level: int
    """
    import logging
    for logger in all_loggers():
        logging.getLogger(logger).setLevel(level)


def add_log_handler(handler):
    """
    Sets the logging handler for all loggers used in the library.

    :param handler: The logging handler to be used, eg. logging.NullHandler
    :type handler: Handler
    """
    import logging
    for logger in all_loggers():
        logging.getLogger(logger).addHandler(handler)
