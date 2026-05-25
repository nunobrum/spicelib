from __future__ import annotations

import io
import re
from pathlib import Path
import logging

from .spice_subcircuit import SpiceCircuit
from .base_editor import BaseEditor
from .primitives import Primitive
from .spice_subcircuit import get_line_command, _is_unique_instruction, separate_lines
from .spice_utils import END_LINE_TERM
from .updates import UpdatePermission, UpdateType

_logger = logging.getLogger("spicelib.SpiceEditor")

class SpiceFile(BaseEditor, SpiceCircuit):
    def __init__(self, netlist_file: Path | str, encoding, **kwargs):
        BaseEditor.__init__(self, netlist_file)
        SpiceCircuit.__init__(self)
        self.encoding = encoding
        self.reset_netlist(**kwargs)

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
        :return: Nothing
        """
        permission = self.begin_update()
        if permission == UpdatePermission.Deny:
            raise PermissionError('The .NET file is read-only')

        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM

        cmd = get_line_command(instruction)
        if _is_unique_instruction(cmd):
            # Before adding new instruction, delete previously set unique instructions
            i = 0
            while i < len(self.netlist):
                line = self.netlist[i]
                if isinstance(line, Primitive) and _is_unique_instruction(line.obj):
                    self.netlist[i] = Primitive(netlist=self, obj=instruction)
                    if permission == UpdatePermission.Inform:
                        self.end_update("INSTRUCTION", instruction.strip(), UpdateType.UpdateInstruction)
                    return
                else:
                    i += 1
        elif cmd == '.PARAM':
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')

        # check whether the instruction is already there (dummy proofing)
        for line in self.netlist:
            if isinstance(line, Primitive) and line.obj.strip() == instruction.strip(): # pyright: ignore[reportOptionalMemberAccess]
                _logger.warning(f'Instruction "{instruction.strip()}" is already present in the netlist. Ignoring addition.')
                return
        # TODO: if adding a .MODEL or .SUBCKT it should verify if it already exists and update it.

        # Insert at the end
        line = len(self.netlist) - 1
        # If there is .backanno, then it will be added just before that statement
        for nr, linecontent in enumerate(self.netlist):
            if isinstance(linecontent, Primitive): # only Primitive can have .backanno
                if linecontent.obj.lower().startswith('.backanno'): # pyright: ignore[reportOptionalMemberAccess]
                    line = nr
                    break

        primitive = self.class_for_instruction(instruction, cmd)
        self.netlist.insert(line, primitive)

        if permission == UpdatePermission.Inform:
            self.end_update("INSTRUCTION", instruction.strip(), UpdateType.AddInstruction)

    def remove_instruction(self, instruction) -> bool:
        # docstring is in the parent class
        permission = self.begin_update()
        if permission == UpdatePermission.Deny:
            raise PermissionError('The .NET file is read-only')
        # TODO: Make it more intelligent so it recognizes .models, .param and .subckt

        i = 0
        for line in self.netlist:
            if isinstance(line, Primitive) and line.obj.strip() == instruction.strip(): # pyright: ignore[reportOptionalMemberAccess]
                del self.netlist[i]
                logtxt = instruction.strip().replace("\r", "\\r").replace("\n", "\\n")
                _logger.info(f'Instruction "{logtxt}" removed')
                if permission == UpdatePermission.Inform:
                    self.end_update('INSTRUCTION', logtxt, UpdateType.DeleteInstruction)
                return True
            # All other cases are ignored
            i += 1

        _logger.error(f'Instruction "{instruction}" not found.')
        return False

    def remove_Xinstruction(self, search_pattern: str) -> bool:
        # docstring is in the parent class
        permission = self.begin_update()
        if permission == UpdatePermission.Deny:
            raise PermissionError('The .NET file is read-only')

        regex = re.compile(search_pattern, re.IGNORECASE)
        i = 0
        instr_removed = False
        while i < len(self.netlist):
            line = self.netlist[i]
            if isinstance(line, Primitive):
                line = line.obj
            if isinstance(line, str) and (match := regex.match(line)):
                del self.netlist[i]
                instr_removed = True
                if  permission == UpdatePermission.Inform:
                    self.end_update('INSTRUCTION', match.string.strip(), UpdateType.DeleteInstruction)
                _logger.info(f'Instruction "{line}" removed')
            else:
                i += 1
        if instr_removed:
            return True
        else:
            _logger.error(f'No instruction matching pattern "{search_pattern}" was found')
            return False

    def save_netlist(self, run_netlist_file: str | Path | io.StringIO) -> None:
        # docstring is in the parent class
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        if isinstance(run_netlist_file, Path):
            f = open(run_netlist_file, 'w', encoding=self.encoding)
        else:
            f = run_netlist_file

        try:
            self.write_lines(f) # pyright: ignore[reportArgumentType]
        finally:
            if not isinstance(f, io.StringIO):
                f.close()

    def save_as(self, new_circuit_filepath: str | Path) -> None:
        """
        Saves the netlist to a new file. The new file will be created if it does not exist, and overwritten if it does exist.

        :param new_circuit_filepath: Path to the new netlist file
        :type new_circuit_filepath: str or Path
        :return: Nothing
        """
        self._circuit_filepath = Path(new_circuit_filepath)
        self.save_netlist(self._circuit_filepath)

    def reset_netlist(self, **kwargs) -> bool:
        """
        Removes all previous edits done to the netlist, i.e. resets it to the original state.

        :returns: True if the netlist is loaded successfully. False is returned in case a .END statement is missing.
        """
        # For some reason, the MRO is not working well here. Need to explicitly call each super class individually.
        SpiceCircuit.reset_netlist(self)
        BaseEditor.reset_netlist(self)
        self.netlist_updates.clear()
        self.update_permission = UpdatePermission.Initializing
        finished = True
        if kwargs.get('create_blank', False):
            self._add_lines(['* netlist generated from spicelib'])
        elif self.circuit_file.exists():
            with open(self.circuit_file, encoding=self.encoding, errors='replace') as f:
                lines = separate_lines(f)  # pyright: ignore[reportArgumentType] # Creates an iterator object to consume the file
                finished = self._add_lines(lines) or kwargs.get('include_file', False)

                # consume any extra lines that may exit
                for line in lines:
                    cmd = get_line_command(line)
                    if cmd == '*':
                        # comments are still acceptable
                        self.netlist.append(line)
                    else:
                        # not expecting any valid primitive after the .END statement
                        _logger.info(f"Ignoring line \"{line}\" found after END statement")

        else:
            _logger.error(f"Netlist file not found: {self.circuit_file}")
        self.update_permission = UpdatePermission.Inform
        return finished  # This means that is finished