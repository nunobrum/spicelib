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
# Name:        spice_editor.py
# Purpose:     Class made to update Generic Spice netlists
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from pathlib import Path
import re
import io
from typing import Union, Callable, Any

from .base_editor import BaseEditor
from .primitives import Primitive
from .spice_components import SpiceComponent
from .spice_utils import END_LINE_TERM
from .updates import UpdateType
from .spice_subcircuit import SpiceCircuit, get_line_command, ControlEditor, _is_unique_instruction
import logging

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


class SpiceEditor(BaseEditor, SpiceCircuit):
    """
    Provides interfaces to manipulate SPICE netlist files. The class doesn't update the netlist file
    itself. After implementing the modifications, the user should call the "save_netlist" method to write a new
    netlist file.

    :param netlist_file: Name of the .NET file to parse
    :type netlist_file: str or pathlib.Path
    :param encoding: Forcing the encoding to be used on the circuit netlile read. Defaults to 'autodetect' which will
        call a function that tries to detect the encoding automatically. This, however, is not 100% foolproof.
    :type encoding: str, optional
    :param create_blank: Create a blank '.net' file when 'netlist_file' not exist. False by default
    :type create_blank: bool, optional
    """

    def __init__(self, netlist_file: Union[str, Path], encoding='autodetect', create_blank=False):
        BaseEditor.__init__(self)
        SpiceCircuit.__init__(self)
        self.netlist_file = Path(netlist_file)
        self._readonly = False
        self.modified_subcircuits = {}
        if create_blank:
            self.encoding = 'utf-8'  # when user want to create a blank netlist file, and didn't set encoding.
        else:
            if encoding == 'autodetect':
                try:
                    self.encoding = detect_encoding(self.netlist_file, r'^\*')  # Normally, the file will start with a '*'
                except EncodingDetectError as err:
                    raise err
            else:
                self.encoding = encoding
        self.reset_netlist(create_blank)

    @property
    def circuit_file(self) -> Path:
        # docstring inherited from BaseSchematic
        return self.netlist_file

    def add_instruction(self, instruction: str) -> None:
        """Adds a SPICE instruction to the netlist.

        For example:

        .. code-block:: text

                  .tran 10m ; makes a transient simulation
                  .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms ; Establishes a measuring
                  .step run 1 100, 1 ; makes the simulation run 100 times
                  .control ... control statements on multiple lines ... .endc

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM
        cmd = get_line_command(instruction)
        if _is_unique_instruction(cmd):
            # Before adding new instruction, delete previously set unique instructions
            i = 0
            while i < len(self.netlist):
                line = self.netlist[i]
                if isinstance(line, Primitive) and _is_unique_instruction(line._obj):
                    self.netlist[i] = Primitive(netlist=self, obj=instruction)
                    return
                else:
                    i += 1
        elif cmd == '.PARAM':
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')
        
        # check whether the instruction is already there (dummy proofing)
        for line in self.netlist:
            if isinstance(line, Primitive) and line._obj.strip() == instruction.strip():
                _logger.warning(f'Instruction "{instruction.strip()}" is already present in the netlist. Ignoring addition.')
                return
        # TODO: if adding a .MODEL or .SUBCKT it should verify if it already exists and update it.

        # Insert at the end
        line = len(self.netlist) - 1
        # If there is .backanno, then it will be added just before that statement
        for nr, linecontent in enumerate(self.netlist):
            if isinstance(linecontent, Primitive): # only Primitive can have .backanno
                if linecontent._obj.lower().startswith('.backanno'):
                    line = nr
                    break

        BaseEditor.add_instruction(self, instruction)

        primitive = self.class_for_instruction(instruction, cmd)
        self.netlist.insert(line, primitive)

    def remove_instruction(self, instruction) -> bool:
        # docstring is in the parent class

        # TODO: Make it more intelligent so it recognizes .models, .param and .subckt

        i = 0
        for line in self.netlist:
            if isinstance(line, Primitive) and line._obj.strip() == instruction.strip():
                del self.netlist[i]
                logtxt = instruction.strip().replace("\r", "\\r").replace("\n", "\\n")
                _logger.info(f'Instruction "{logtxt}" removed')
                self.add_update('INSTRUCTION', logtxt, UpdateType.DeleteInstruction)
                return True
            # All other cases are ignored
            i += 1
        
        _logger.error(f'Instruction "{instruction}" not found.')
        return False

    def remove_Xinstruction(self, search_pattern: str) -> bool:
        # docstring is in the parent class
        regex = re.compile(search_pattern, re.IGNORECASE)
        i = 0
        instr_removed = False
        while i < len(self.netlist):
            line = self.netlist[i]
            if isinstance(line, Primitive):
                line = line._obj
            if isinstance(line, str) and (match := regex.match(line)):
                del self.netlist[i]
                instr_removed = True
                self.add_update('INSTRUCTION', match.string.strip(), UpdateType.DeleteInstruction)
                _logger.info(f'Instruction "{line}" removed')
            else:
                i += 1
        if instr_removed:
            return True
        else:
            _logger.error(f'No instruction matching pattern "{search_pattern}" was found')
            return False

    def save_netlist(self, run_netlist_file: Union[str, Path, io.StringIO]) -> None:
        # docstring is in the parent class
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        if isinstance(run_netlist_file, Path):
            f = open(run_netlist_file, 'w', encoding=self.encoding)
        else:
            f = run_netlist_file

        try:
            for primitive in self.netlist:
                if isinstance(primitive, str):
                    f.write(primitive)
                elif isinstance(primitive, (SpiceComponent, SpiceCircuit, ControlEditor)):
                    primitive.write_lines(f)
                elif isinstance(primitive, Primitive):
                    line = primitive._obj
                    # Writes the modified sub-circuits at the end just before the .END clause
                    if line.upper().startswith(".END"):
                        # write here the modified sub-circuits
                        for sub in self.modified_subcircuits.values():
                            sub.write_lines(f)
                    f.write(line)
                else:
                    raise RuntimeError("Unknown primitive type found in netlist")
        finally:
            if not isinstance(f, io.StringIO):
                f.close()

    def get_control_sections(self) -> list[str]:
        """
        Returns a list representing the control sections in the netlist.
        Control sections are all anonymous, so they do not have a name, just an index.
        They are also not parsed, they are just a list of strings (with embedded newlines).

        :return: list of control section strings. These strings have each multiple lines, start with ``.CONTROL`` and end with ``.ENDC``.
        :rtype: list[str]
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
        :type instruction: str
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
        :type index: int
        :returns: True if the control section was found and removed, False otherwise
        :rtype: bool
        """
        if index < 0:
            raise IndexError("Control section index out of range")
        i = 0
        for nr, line in enumerate(self.netlist):
            if isinstance(line, ControlEditor):
                if i == index:
                    del self.netlist[nr]
                    logtxt = line.content.replace("\r", "\\r").replace("\n", "\\n")
                    self.add_update('INSTRUCTION', logtxt, UpdateType.DeleteInstruction)
                    _logger.info(f"Control section {index} removed")
                    return True
                i += 1
        _logger.error(f"Control section {index} was not found")
        return False
    
    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Removes all previous edits done to the netlist, i.e. resets it to the original state.

        :returns: Nothing
        """
        super().reset_netlist(create_blank)
        self.modified_subcircuits.clear()
        if create_blank:
            lines = ['* netlist generated from spicelib', '.end']
            finished = self._add_lines(lines)
            if not finished:
                raise SyntaxError("Netlist with missing .END or .ENDS statements")
        elif self.netlist_file.exists():
            with open(self.netlist_file, 'r', encoding=self.encoding, errors='replace') as f:
                lines = iter(f)  # Creates an iterator object to consume the file
                finished = self._add_lines(lines)
                if not finished:
                    raise SyntaxError("Netlist with missing .END or .ENDS statements")
                # else:
                #     for _ in lines:  # Consuming the rest of the file.
                #         pass  # print("Ignoring %s" % _)
        else:
            _logger.error("Netlist file not found: {}".format(self.netlist_file))

    def run(self, wait_resource: bool = True,
            callback: Callable[[str, str], Any] = None, timeout: float = None, run_filename: str = None, simulator=None):
        """
        .. deprecated:: 1.0 Use the `run` method from the `SimRunner` class instead.

        Convenience function for maintaining legacy with legacy code. Runs the SPICE simulation.
        """
        from ..sim.sim_runner import SimRunner
        runner = SimRunner(simulator=simulator)
        return runner.run(self, wait_resource=wait_resource, callback=callback, timeout=timeout, run_filename=run_filename)
