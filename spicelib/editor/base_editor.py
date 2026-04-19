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

from abc import abstractmethod, ABC
from pathlib import Path
import logging
import os
import io
from typing import TypeAlias, Final

from ..sim.simulator import Simulator
from .updates import Updates, UpdateType, UpdatePermission

_logger = logging.getLogger("spicelib.BaseEditor")

ValueType: TypeAlias = str | float | int | complex

SUBCKT_DIVIDER: Final[str] = ':'  #: This controls the sub-circuit divider when setting component values inside sub-circuits.
# Ex: Editor.set_component_value('XU1:R1', '1k')

def PARAM_REGEX(pname):
    return r"(?P<name>" + pname + r")\s*[= ]\s*(?P<value>(?P<cb>\{)?(?(cb)[^\}]*\}|(?P<st>\")?(?(st)[^\"]*\"|[\d\.\+\-Ee]+[a-zA-Z%]*)))"


class BaseEditor(ABC):
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

    def __init__(self, circuit_filepath) -> None:
        self._circuit_filepath: Path = Path(circuit_filepath)
        self.netlist_updates = Updates()  # Keep track of updates
        self.update_permission: UpdatePermission = UpdatePermission.Initializing   # Whether to record updates or not.
        # This is useful when we want to make changes to the netlist without recording them as updates
        # (e.g. when resetting the netlist)

    @property
    def circuit_file(self) -> Path:
        """Returns the path of the circuit file."""
        return self._circuit_filepath

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist will be reset to a new empty netlist. If False, the netlist will be
                             reset to the original state.
        """
        self.netlist_updates.clear()
        self.update_permission = UpdatePermission.Initializing

    @abstractmethod
    def save_netlist(self, run_netlist_file: str | Path | io.StringIO) -> None:
        """
        Saves the current state of the netlist to a file or a string.
        :param run_netlist_file: File name of the netlist file, or a StringIO object.
        :returns: Nothing
        """
        ...

    def write_netlist(self, run_netlist_file: str | Path) -> None:
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
        """
        return self.update_permission == UpdatePermission.Deny

    @abstractmethod
    def add_instruction(self, instruction: str) -> None:
        """
        Adds a SPICE instruction to the netlist.

        For example:

            .. code-block:: text

                .tran 10m ; makes a transient simulation
                .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms ; Establishes a measuring
                .step run 1 100, 1 ; makes the simulation run 100 times

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :return: Nothing
        """
        ...

    @abstractmethod
    def remove_instruction(self, instruction: str) -> bool:
        """
        Removes a SPICE instruction from the netlist.

        Example:

        .. code-block:: python

            editor.remove_instruction(".STEP run -1 1023 1")

        This only works if the entire given instruction is contained in a line on the netlist.
        It uses the 'in' comparison, and is case-sensitive.
        It will remove 1 instruction at most, even if more than one could be found.
        `remove_Xinstruction()` is a more flexible way to remove instructions from the netlist.

        :param instruction: The instruction to remove.
        :returns: True if the instruction was found and removed, False otherwise
        """
        ...

    @abstractmethod
    def remove_Xinstruction(self, search_pattern: str) -> bool:
        """
        Removes a SPICE instruction from the netlist based on a search pattern. This is a more flexible way to remove
        instructions from the netlist. The search pattern is a regular expression that will be used to match the
        instructions to be removed. The search pattern is case-insensitive, and will be applied to each line of the netlist.
        All matching lines will be removed.

        Example: The code below will remove all AC analysis instructions from the netlist.

        .. code-block:: python

            editor.remove_Xinstruction(r"\\.AC.*")

        :param search_pattern: Pattern for the instruction to remove. In general, it is best to use a raw string (r).
        :returns: True if the instruction was found and removed, False otherwise
        """
        ...

    def add_instructions(self, *instructions) -> None:
        """
        Adds a list of instructions to the SPICE NETLIST.

        Example:

        .. code-block:: python

            editor.add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")

        :param instructions: Argument list of instructions to add
        :returns: Nothing
        """
        for instruction in instructions:
            self.add_instruction(instruction)
