#!/usr/bin/env python
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        spice_editor.py
# Purpose:     Class made to update Generic Spice netlists
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# License:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from __future__ import annotations

import logging

from pathlib import Path

from .spice_file import SpiceFile
from ..sim.process_callback import CallbackType

from .base_editor import BaseEditor
from .updates import UpdateType, UpdatePermission
from .spice_subcircuit import SpiceCircuit, ControlEditor

from ..utils.detect_encoding import detect_encoding, EncodingDetectError

_logger = logging.getLogger("spicelib.SpiceEditor")

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"



# A Spice netlist can only have one of the instructions below, otherwise an error will be raised

# All the regular expressions here may or may not include leading or trailing spaces
# This means that when you re-assemble parts, you need to be careful to preserve spaces when needed.
# See _insert_section()


# component_replace_regexs = {prefix: re.compile(pattern, re.IGNORECASE) for prefix, pattern in REPLACE_REGEXS.items()}

# The following variable deprecated, and here only so that people can find it.
# It is replaced by SpiceEditor.set_custom_library_paths().
# Since I cannot keep it operational easily, I do not use the deprecated decorator or the magic from https://stackoverflow.com/a/922693.
#
# LibSearchPaths = []


class SpiceEditor(SpiceFile):
    """
    Provides interfaces to manipulate SPICE netlist files. The class doesn't update the netlist file
    itself. After implementing the modifications, the user should call the "save_netlist" method to write a new
    netlist file.

    :param netlist_file: Name of the .NET file to parse
    :param encoding: Forcing the encoding to be used on the circuit netlist file read. Defaults to 'autodetect' which will
        call a function that tries to detect the encoding automatically. This, however, is not 100% foolproof.
    :keyword create_blank: Create a blank '.net' file when 'netlist_file' not exist. False by default
    :keyword include_file: If an include file is being parsed, the control of the ending .END statement is suppressed.
    """

    def __init__(self, netlist_file: Path | str, encoding='autodetect', **kwargs):
        if kwargs.get('create_blank', False):
            if encoding == 'autodetect':
                encoding = 'utf-8'
            else:
                encoding = encoding
        else:
            if encoding == 'autodetect':
                try:
                    encoding = detect_encoding(netlist_file, r'^(?:\*|\.title)')  # Normally, the file will start with a '*' except for KiCad that can start with '.title'
                except EncodingDetectError as err:
                    raise err
        super().__init__(netlist_file, encoding, **kwargs)

    def reset_netlist(self, **kwargs) -> bool:
        """
        Reset the netlist state and reload or reinitialize its content.

        :keyword create_blank: Create a blank '.net' file when 'netlist_file' not exist.
        :keyword include_file: If an include file is being parsed, the control of the ending .END statement is
            suppressed. This is useful when parsing include files, which do not have an .END statement, but are just
            a part of the netlist.
        :return: True if successful, False otherwise.
        """
        finished = super().reset_netlist(**kwargs)
        if kwargs.get('create_blank', False):
            self._add_lines(['.END'])
        else:
            if not finished:
                raise SyntaxError("Netlist with missing .END or .ENDS statements")

            if not self.custom_lib_paths:
                # See if it can find a comment specifying who generated this netlist, only checks the first
                # 5 lines
                lib_paths = None
                for line in self.netlist[:5]:
                    if isinstance(line, str):
                        line_stripped_upped = line.strip().upper()
                        if line.startswith('*'):
                            if line_stripped_upped.endswith(".ASC"):
                                from ..simulators.ltspice_simulator import LTspice
                                lib_paths = LTspice.get_default_library_paths()
                                _logger.info(f"Found LTspice netlist pattern.\nAdding search paths: [{lib_paths}]")
                                break
                            elif line_stripped_upped.endswith(".QSCH"):
                                from ..simulators.qspice_simulator import Qspice
                                lib_paths = Qspice.get_default_library_paths()
                                _logger.info(f"Found Qspice netlist pattern.\nAdding search paths: [{lib_paths}]")
                                break
                            elif 'XYCE' in line_stripped_upped:
                                from ..simulators.xyce_simulator import XyceSimulator
                                lib_paths = XyceSimulator.get_default_library_paths()
                                _logger.info(f"Found Xyce netlist pattern.\nAdding search paths: [{lib_paths}]")
                                break
                            elif 'NGSPICE' in line_stripped_upped:
                                from ..simulators.ngspice_simulator import NGspiceSimulator
                                lib_paths = NGspiceSimulator.get_default_library_paths()
                                _logger.info(f"Found NGspice netlist pattern.\nAdding search paths: [{lib_paths}]")
                                break
                if lib_paths:
                    self.set_custom_library_paths(lib_paths)

        return finished

    def get_control_sections(self) -> list[str]:
        """
        Returns a list representing the control sections in the netlist.
        Control sections are all anonymous, so they do not have a name, just an index.
        They are also not parsed, they are just a list of strings (with embedded newlines).

        :return: list of control section strings. These strings have each multiple lines, start with ``.CONTROL`` and end with ``.ENDC``.
        """
        control_sections = []
        for line in self.netlist:
            if isinstance(line, ControlEditor):
                control_sections.append(line.content)
        return control_sections
    
    def add_control_section(self, instruction: str) -> None:
        """
        Adds a control section to the netlist. The instruction should be a multi-line string that starts with '.CONTROL' and ends with '.ENDC'.
        It will be added as a ControlEditor object to the netlist.
        
        You can also use the `add_instruction()` method, but that method has less checking of the format.
        
        :param instruction: control section instruction
        :raises ValueError: if the instruction does not start with ``.CONTROL`` or does not end with ``.ENDC``
        """
        instruction = instruction.strip()
        if not instruction.upper().startswith('.CONTROL') or not instruction.upper().endswith('.ENDC'):
            raise ValueError("Control section must start with '.CONTROL' and end with '.ENDC'")        
        self.add_instruction(instruction)
                
    def remove_control_section(self, index: int = 0) -> bool:
        """
        Removes a control section from the netlist, based on the index in `get_control_sections()`.
        You can also use `remove_instruction()`, but there, the given text must match the entire control section.
        
        :param index: index of the control section to remove, according to `get_control_sections()`
        :returns: True if the control section was found and removed, False otherwise
        """
        permission = self.begin_update()
        if permission == UpdatePermission.Deny:
            raise PermissionError('The .NET file is read-only')
        if index < 0:
            raise IndexError("Control section index out of range")
        i = 0
        for nr, line in enumerate(self.netlist):
            if isinstance(line, ControlEditor):
                if i == index:
                    del self.netlist[nr]
                    logtxt = line.content.replace("\r", "\\r").replace("\n", "\\n")
                    if permission == UpdatePermission.Inform:
                        self.end_update('INSTRUCTION', logtxt, UpdateType.DeleteInstruction)
                    _logger.info(f"Control section {index} removed")
                    return True
                i += 1
        _logger.error(f"Control section {index} was not found")
        return False

    def run(self, wait_resource: bool = True,
            callback: CallbackType | None = None, timeout: float | None = None, run_filename: str | None = None, simulator=None):
        """
        .. deprecated:: 1.0 Use the `run` method from the `SimRunner` class instead.

        Convenience function for maintaining legacy with legacy code. Runs the SPICE simulation.
        """
        from ..sim.sim_runner import SimRunner
        runner = SimRunner(simulator=simulator)
        return runner.run(self, wait_resource=wait_resource, callback=callback, timeout=timeout, run_filename=run_filename)

    @classmethod
    def add_library_search_paths(cls, *paths) -> None:
        """
        .. deprecated:: 1.1.4 Use the class method `set_custom_library_paths()` instead.

        Adds search paths for libraries. By default, the local directory and the
        ~username/"Documents/LTspiceXVII/lib/sub will be searched forehand. Only when a library is not found in these
        paths then the paths added by this method will be searched.

        :param paths: Path to add to the Search path
        :type paths: str
        :return: Nothing
        """
        cls.set_custom_library_paths(*paths)
