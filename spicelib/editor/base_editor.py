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
# Name:        base_editor.py
# Purpose:     Abstract class that defines the protocol for the editors
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__version__ = "0.1.0"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

from abc import abstractmethod
from pathlib import Path
from typing import Union
import logging
import os
import io

from .base_subcircuit import BaseSubCircuit
from .updates import UpdateType, Updates
from ..sim.simulator import Simulator


_logger = logging.getLogger("spicelib.BaseEditor")

SUBCKT_DIVIDER = ':'  #: This controls the sub-circuit divider when setting component values inside sub-circuits.
# Ex: Editor.set_component_value('XU1:R1', '1k')

def PARAM_REGEX(pname):
    return r"(?P<name>" + pname + r")\s*[= ]\s*(?P<value>(?P<cb>\{)?(?(cb)[^\}]*\}|(?P<st>\")?(?(st)[^\"]*\"|[\d\.\+\-Ee]+[a-zA-Z%]*)))"


class BaseEditor(BaseSubCircuit):
    """
    This defines the primitives (protocol) to be used for both SpiceEditor and AscEditor
    classes.
    """
    custom_lib_paths: list[str] = []
    """The custom library paths. Not to be modified, only set via `set_custom_library_paths()`.
    This is a class variable, so it will be shared between all instances
    
    :meta hide-value:"""    
    simulator_lib_paths: list[str] = []
    """ This is initialised with typical locations found for your simulator.
    You can (and should, if you use wine), call `prepare_for_simulator()` once you've set the executable paths.
    This is a class variable, so it will be shared between all instances.
    
    :meta hide-value:
    """

    def __init__(self):
        """Initializing the list that contains all the modifications done to a netlist."""
        self.netlist_updates = Updates()

    def add_update(self, name: str, value: Union[str, int, float, None], updates: UpdateType):
        self.netlist_updates.add_update(name, value, updates)

    @property
    @abstractmethod
    def circuit_file(self) -> Path:
        """Returns the path of the circuit file."""
        ...

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist will be reset to a new empty netlist. If False, the netlist will be
                             reset to the original state.
        """
        self.netlist_updates.clear()

    @abstractmethod
    def save_netlist(self, run_netlist_file: Union[str, Path, io.StringIO]) -> None:
        """
        Saves the current state of the netlist to a file or a string.
        :param run_netlist_file: File name of the netlist file, or a StringIO object.
        :type run_netlist_file: pathlib.Path or str or io.StringIO
        :returns: Nothing
        """
        ...

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        """
        .. deprecated:: 1.x Use `save_netlist()` instead.

        Writes the netlist to a file. This is an alias to save_netlist."""
        self.save_netlist(run_netlist_file)

    @classmethod     
    def prepare_for_simulator(cls, simulator: Simulator) -> None:
        """
        Sets the library paths that should be correct for the simulator object. 
        The simulator object should have had the executable path (spice_exe) set correctly.
        
        This is especially useful in 2 cases:
            * when the simulator is running under wine, as it is difficult to detect \
                the correct library paths in that case.
            * when the editor can be used with different simulators, that have different library paths.
        
        Note:
            * you can always also set the library paths manually via `set_custom_library_paths()`
            * this method is a class method and will affect all instances of the class

        :param simulator: Simulator object from which the library paths will be taken.
        :type simulator: Simulator
        :returns: Nothing
        """
        if simulator is None:
            raise NotImplementedError("The prepare_for_simulator method requires a simulator object")
        cls.simulator_lib_paths = simulator.get_default_library_paths()
        return
    
    @classmethod
    def _check_and_append_custom_library_path(cls, path) -> None:
        """:meta private:"""
        if path.startswith("~"):
            path = os.path.expanduser(path)
            
        if os.path.exists(path) and os.path.isdir(path):
            _logger.debug(f"Adding path '{path}' to the custom library path list")
            cls.custom_lib_paths.append(path)
        else:
            _logger.warning(f"Cannot add path '{path}' to the custom library path list, as it does not exist")            

    @classmethod
    def set_custom_library_paths(cls, *paths) -> None:
        """
        Set the given library search paths to the list of directories to search when needed.
        It will delete any previous list of custom paths, but will not affect the default paths 
        (be it from `init()` or from `prepare_for_simulator()`).
        
        Note that this method is a class method and will affect all instances of the class.

        :param paths: Path(s) to add to the Search path
        :return: Nothing    
        """
        # empty the list
        cls.custom_lib_paths = []
        # and then fill it with the new paths
        for path in paths:
            if isinstance(path, str):
                cls._check_and_append_custom_library_path(path)
            elif isinstance(path, list):
                for p in path:
                    cls._check_and_append_custom_library_path(p)
            
    def is_read_only(self) -> bool:
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        return False



