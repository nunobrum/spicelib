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
# Name:        spice_subcircuit.py
# Purpose:     Representation and parsing of SPICE subcircuits
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import io
import os
import re
from pathlib import Path
from typing import Union, Optional
import logging



from .editor_errors import *
from .spice_utils import subckt_regex, SUBCKT_CLAUSE_FIND, \
    lib_inc_regex, END_LINE_TERM, REPLACE_REGEXS, VALID_PREFIXES, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
from .primitives import Primitive, format_eng
from .updates import UpdateType
from .base_subcircuit import BaseSubCircuit
from .spice_components import SpiceComponent, component_replace_regexs, _insert_section
from .spice_subcircuit_instance import SpiceCircuitInstance
from .base_editor import SUBCKT_DIVIDER, PARAM_REGEX, BaseEditor

from spicelib.utils.detect_encoding import detect_encoding, EncodingDetectError
from spicelib.utils.file_search import search_file_in_containers

def get_line_command(line) -> str:
    """
    Retrieves the type of SPICE command in the line.
    Starts by removing the leading spaces and the evaluates if it is a comment, a directive or a component.
    """
    if isinstance(line, str):
        for i in range(len(line)):
            ch = line[i]
            if ch == ' ' or ch == '\t':
                continue
            else:
                ch = ch.upper()
                if ch in VALID_PREFIXES:  # A circuit element
                    return ch
                elif ch == '+':
                    return '+'  # This is a line continuation.
                elif ch in "#;*\n\r":  # It is a comment or a blank line
                    return "*"
                elif ch == '.':  # this is a directive
                    j = i + 1
                    while j < len(line) and (line[j] not in (' ', '\t', '\r', '\n')):
                        j += 1
                    return line[i:j].upper()
                else:
                    raise SyntaxError(f"Unrecognized command in line: \"{line}\"")
    elif isinstance(line, SpiceCircuit):
        return ".SUBCKT"
    elif isinstance(line, ControlEditor):
        return ".CONTROL"
    elif isinstance(line, (SpiceComponent, SpiceCircuitInstance)):
        return line._obj[0]
    elif isinstance(line, Primitive):
        return get_line_command(line._obj)
    else:
        raise SyntaxError('Unrecognized command in line "{}"'.format(line))


def _is_unique_instruction(instruction):
    """
    (Private function. Not to be used directly)
    Returns true if the instruction is one of the unique instructions
    """
    cmd = get_line_command(instruction)
    return cmd in UNIQUE_SIMULATION_DOT_INSTRUCTIONS

_logger = logging.getLogger("spicelib.SpiceEditor")

class SpiceCircuit(BaseSubCircuit):
    """
    Represents sub-circuits within a SPICE circuit. Since sub-circuits can have sub-circuits inside
    them, it serves as base for the top level netlist. This hierarchical approach helps to encapsulate
    and protect parameters and components from edits made at a higher level.
    """

    simulator_lib_paths: list[str] = []
    """ This is initialised with typical locations found for LTspice.
    You can (and should, if you use wine), call `prepare_for_simulator()` once you've set the executable paths.
    This is a class variable, so it will be shared between all instances.
    
    :meta hide-value:
    """

    def __init__(self, parent: "SpiceCircuit" = None):
        super().__init__()
        self.netlist = []
        self.parent = parent

    def add_update(self, name: str, value: Union[str, int, float, None], updates: UpdateType):
        """
        Notifies the netlist that a component has been updated. This will serve to keep track of changes.
        of modified subcircuits and the updates done to the netlist.

        :param name: The name of the component that was updated.
        :type name: str
        :param value: The new value of the component.
        :type value: Union[str, int, float, None]
        :param updates: The type of update that occurred.
        :type updates: UpdateType
        """
        if self.recording_updates:
            if len(self.netlist_updates) == 0 and self.parent is not None:   # This is the first update
                subckt_name = self.name()
                self.parent.add_update(subckt_name, subckt_name, UpdateType.CloneSubcircuit)
            self.netlist_updates.add_update(name, value, updates)

    @property
    def was_modified(self) -> bool:
        return len(self.netlist_updates) > 0

    def _add_lines(self, line_iter):
        """Internal function. Do not use.
        Add a list of lines to the netlist."""
        self.recording_updates = False
        for line in line_iter:
            cmd = get_line_command(line)
            # cmd is guaranteed to be uppercased
            if cmd == '.SUBCKT':
                sub_circuit = SpiceCircuit(self)
                primitive = Primitive(netlist=self, obj=line)
                sub_circuit.netlist.append(primitive)
                # Advance to the next non nested .ENDS
                finished = sub_circuit._add_lines(line_iter)
                if finished:
                    self.netlist.append(sub_circuit)
                else:
                    return False
            elif cmd == ".CONTROL":
                sub_circuit = ControlEditor(self)
                sub_circuit.content = line
                # Advance to the next .ENDC. There is no risk of nesting, as control sections cannot be nested.
                finished = sub_circuit._add_lines(line_iter)
                if finished:
                    self.netlist.append(sub_circuit)
                else:
                    return False
            elif cmd == '+':
                assert len(self.netlist) > 0, "ERROR: The first line cannot be starting with a +"
                # Concatenate the line to the previous line. Make it easy to handle: just make it 1 line. (but keep spaces etc)
                self.netlist[-1]+=line  # Append to the last line, but remove the preceding newline and the leading '+'
            elif len(cmd) == 1 and cmd in VALID_PREFIXES:
                # This is a component line
                if cmd == 'X':
                    component = SpiceCircuitInstance(netlist=self, obj=line)
                else:
                    component = SpiceComponent(netlist=self, obj=line)
                self.netlist.append(component)
            elif cmd == '*':
                # This is a comment or blank line
                self.netlist.append(line)
            else:
                primitive = Primitive(netlist=self, obj=line)
                self.netlist.append(primitive)
                if cmd[:4] == '.END':  # True for either .END, .ENDS and .ENDC primitives
                    # Now construct the sub-circuit object
                    for component in self.netlist:
                        if isinstance(component, (SpiceComponent, SpiceCircuitInstance)):
                            component.reset_attributes()
                    self.recording_updates = True
                    return True  # If a sub-circuit is ended correctly, returns True
        return False  # If a sub-circuit ends abruptly, returns False

    def write_lines(self, stream: io.StringIO) -> None:
        """Internal function. Do not use."""
        # This helper function writes the contents of sub-circuit to the file stream
        for primitive in self.netlist:
            if isinstance(primitive, str):
                line = primitive
                # TODO: All dot instructions should be Primitives. Only comments and blank lines should be strings.
                # Writes the modified sub-circuits at the end just before the .END clause
                if line.upper().startswith(".END"):
                    # write here the modified sub-circuits
                    for sub in self.modified_subcircuits():
                        sub.write_lines(stream)
                stream.write(primitive)
            elif isinstance(primitive, (SpiceComponent, SpiceCircuit, ControlEditor)):
                primitive.write_lines(stream)
            elif isinstance(primitive, Primitive):
                line = primitive._obj
                # Writes the modified sub-circuits at the end just before the .END clause
                if line.upper().startswith(".END"):
                    # write here the modified sub-circuits
                    for sub in self.modified_subcircuits():
                        sub.write_lines(stream)
                stream.write(line)
            else:
                raise RuntimeError("Unknown primitive type found in netlist")

    def _get_parameter_named(self, param_name) -> tuple[int, Union[re.Match, None]]:
        """
        Internal function. Do not use. Returns a line starting with command and matching the search with the regular
        expression
        """
        search_expression = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        param_name_upped = param_name.upper()
        line_no = 0
        while line_no < len(self.netlist):
            line = self.netlist[line_no]
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                line_no += 1
                continue
            elif isinstance(line, ControlEditor):  # same for control editor
                line_no += 1
                continue
            elif isinstance(line, Primitive):
                line = line._obj
            cmd = get_line_command(line)
            if cmd == '.PARAM':
                matches = search_expression.finditer(line)
                for match in matches:
                    if match.group("name").upper() == param_name_upped:
                        return line_no, match
            line_no += 1
        return -1, None  # If it fails, it returns an invalid line number and No match

    def get_all_parameter_names(self) -> list[str]:
        # docstring inherited from BaseEditor
        param_names = []
        search_expression = re.compile(PARAM_REGEX(r"\w+"), re.IGNORECASE)
        for line in self.netlist:
            if isinstance(line, Primitive):
                line = line._obj
            cmd = get_line_command(line)
            if cmd == '.PARAM':
                matches = search_expression.finditer(line)
                for match in matches:
                    param_name = match.group('name')
                    param_names.append(param_name.upper())
        return sorted(param_names)

    def get_subcircuit_names(self) -> list[str]:
        """
        Returns a list of the names of the sub-circuits in the netlist.

        :return: list of sub-circuit names
        :rtype: list[str]
        """

        subckt_names = []
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):
                subckt_names.append(line.name())
        return subckt_names

    def get_subcircuit_named(self, name: str) -> Optional['SpiceCircuit']:
        """
        Returns the sub-circuit object with the given name.

        :param name: name of the subcircuit
        :type name: str
        :return: _description_
        :rtype: _type_
        """

        for line in self.netlist:
            if isinstance(line, SpiceCircuit):
                if line.name() == name:
                    return line
        if self.parent is not None:
            return self.parent.get_subcircuit_named(name)
        return None

    def get_subcircuit(self, instance_name: str) -> 'SpiceCircuit':
        """
        Returns an object representing a Subcircuit. This object can manipulate elements such as the SpiceEditor does.

        :param instance_name: Reference of the subcircuit
        :type instance_name: str
        :returns: SpiceCircuit instance
        :rtype: SpiceCircuit
        :raises UnrecognizedSyntaxError: when an spice command is not recognized by spicelib
        :raises ComponentNotFoundError: When the reference was not found
        """
        sub_inst = self.get_component(instance_name)
        assert isinstance(sub_inst, SpiceCircuitInstance)
        return sub_inst.subcircuit

    def reset_netlist(self, create_blank: bool = False) -> None:
        """
        Reverts all changes done to the netlist. If create_blank is set to True, then the netlist is blanked.

        :param create_blank: If True, the netlist is blanked. That is, all primitives and components are erased.
        :type create_blank: bool
        :returns: None
        """
        super().reset_netlist()
        self.netlist.clear()

    def clone(self, new_parent, **kwargs) -> 'SpiceCircuit':
        """
        Creates a new copy of the SpiceCircuit. Changes done at the new copy do not affect the original.

        :key new_name: The new name to be given to the circuit
        :key type new_name: str
        :return: The new replica of the SpiceCircuit object
        :rtype: SpiceCircuit
        """
        clone = SpiceCircuit(new_parent)
        clone.netlist.append( "***** SpiceEditor Manipulated this sub-circuit ****" + END_LINE_TERM)
        for primitive in self.netlist:
            if isinstance(primitive, SpiceCircuit):
                clone.netlist.append(primitive.clone(clone))
            elif isinstance(primitive, SpiceComponent):
                clone.netlist.append(primitive.clone(clone))
            elif isinstance(primitive, Primitive):
                clone.netlist.append(Primitive(netlist=clone, obj=primitive._obj))
            else:
                clone.netlist.append(primitive)
        clone.netlist.append("***** ENDS SpiceEditor ****" + END_LINE_TERM)
        new_name = kwargs.get('new_name', None)
        if new_name is not None and isinstance(new_name, str):
            clone.setname(new_name)
        clone.recording_updates = True
        return clone

    def name(self) -> str:
        """
        Returns the name of the Sub-Circuit.

        :rtype: str
        """
        if len(self.netlist):
            for line in self.netlist:
                if isinstance(line, Primitive):
                    line = line._obj
                m = subckt_regex.search(line)
                if m:
                    return m.group('name')
            else:
                raise RuntimeError("Unable to find .SUBCKT clause in subcircuit")
        else:
            raise RuntimeError("Empty Subcircuit")

    def setname(self, new_name: str):
        """
        Renames the sub-circuit to a new name. No check is done to the new name.
        It is up to the user to make sure that the new name is valid.

        :param new_name: The new Name.
        :type new_name: str
        :return: Nothing
        """
        if len(self.netlist):
            lines = len(self.netlist)
            line_no = 0
            while line_no < lines:
                line = self.netlist[line_no]
                if isinstance(line, Primitive):
                    line = line._obj
                m = subckt_regex.search(line)
                if m:
                    # Replacing the name in the SUBCKT Clause
                    start = m.start('name')
                    end = m.end('name')
                    # print(f"Replacing '{line[start:end]}' with '{new_name}'")
                    self.netlist[line_no] = _insert_section(line, start, end, new_name) + END_LINE_TERM
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")

            # This second loop finds the .ENDS clause
            while line_no < lines:
                line = self.netlist[line_no]
                if isinstance(line, Primitive):
                    line = line._obj
                if get_line_command(line) == '.ENDS':
                    self.netlist[line_no] = '.ENDS ' + new_name + END_LINE_TERM
                    break
                line_no += 1
            else:
                raise MissingExpectedClauseError("Unable to find .SUBCKT clause in subcircuit")
        else:
            # Avoiding exception by creating an empty sub-circuit
            self.netlist.append("* SpiceEditor Created this sub-circuit")
            self.netlist.append(Primitive(netlist=self, obj='.SUBCKT %s%s' % (new_name, END_LINE_TERM)))
            self.netlist.append(Primitive(netlist=self, obj='.ENDS %s%s' % (new_name, END_LINE_TERM)))

    def get_component(self, reference: str) -> Union[SpiceComponent, 'SpiceCircuit']:
        """
        Returns an object representing the given reference in the schematic file.

        :param reference: Reference of the component
        :type reference: str
        :return: The SpiceComponent object or a SpiceSubcircuit in case of hierarchical design
        :rtype: SpiceComponent or SpiceCircuit
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        ref_upped = reference.upper()
        if SUBCKT_DIVIDER in ref_upped:
            if ref_upped[0] != 'X':  # It needs be contained in a sub-circuit declaration
                raise ComponentNotFoundError("Only subcircuits can have components inside.")
            else:
                # In this case the sub-circuit needs to be copied so that is copy is modified.
                # A copy is created for each instance of a sub-circuit.
                subckt_ref, sub_ref = ref_upped.split(SUBCKT_DIVIDER, 1)
                subcircuit_instance = self.get_component(subckt_ref)
                return subcircuit_instance.get_component(sub_ref)
        else:
            for component in self.netlist:
                if isinstance(component, SpiceComponent):
                    if component.reference.upper() == ref_upped:
                        return component
                elif isinstance(component, SpiceCircuitInstance):
                    name = component.name()
                    if name.upper() == ref_upped:
                        return component

            error_msg = "line starting with '%s' not found in netlist" % reference
            _logger.error(error_msg)
            raise ComponentNotFoundError(error_msg)


    def __getitem__(self, item) -> SpiceComponent:
        component = super().__getitem__(item)
        return component

    def __delitem__(self, key):
        """
        This method allows the user to delete a component using the syntax:
        del circuit['R1']
        """
        self.remove_component(key)

    def __contains__(self, key):
        """
        This method allows the user to check if a component is in the circuit using the syntax:
        'R1' in circuit
        """
        try:
            self.get_component(key)
            return True
        except ComponentNotFoundError:
            return False

    def __iter__(self):
        """
        This method allows the user to iterate over the components in the circuit using the syntax:
        for component in circuit:
            print(component)
        """
        for line_no, line in enumerate(self.netlist):
            if isinstance(line, SpiceCircuit):
                yield from line
            elif isinstance(line, ControlEditor):
                continue  # no components here, just control commands
            else:
                cmd = get_line_command(line)
                if cmd in VALID_PREFIXES:
                    yield SpiceComponent(self, line_no)

    def get_component_attribute(self, reference: str, attribute: str) -> Optional[str]:
        """
        Returns the attribute of a component retrieved from the netlist.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
        :raises: UnrecognizedSyntaxError when the line doesn't match the expected REGEX.
        :raises: NotImplementedError if there isn't an associated regular expression for the component prefix.
        """
        component = self.get_component(reference)
        if isinstance(component, SpiceCircuit):
            raise ValueError(f"Component '{reference}' is a sub-circuit. Use get_subcircuit() instead.")
        else:
            return component.get_(attribute, None)

    def get_component_parameters(self, reference: str) -> dict:
        # docstring inherited from BaseEditor
        component = self.get_component(reference)
        answer = {}
        answer.update(component.params)
        # Now check if there is a value parameter
        # NOTE: This is a legacy behavior that may be removed in future versions.
        if hasattr(component, 'value'):
            answer['Value'] = component.value_str
        return answer

    def set_component_parameters(self, reference: str, **kwargs) -> None:
        # docstring inherited from BaseEditor
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        self.get_component(reference).set_parameters(**kwargs)

    def get_parameter(self, param: str) -> str:
        """
        Returns the value of a parameter retrieved from the netlist.

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """

        line_no, match = self._get_parameter_named(param)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(param)

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        """Sets the value of a parameter in the netlist. If the parameter is not found, it is added to the netlist.

        Usage: ::

         runner.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in its usage
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        param_line, match = self._get_parameter_named(param)
        super().set_parameter(param, value)
        if isinstance(value, (int, float)):
            value_str = format_eng(value)
        else:
            value_str = value
        if match:
            start, stop = match.span('value')
            if isinstance(self.netlist[param_line], Primitive):
                self.netlist[param_line]._obj = _insert_section(self.netlist[param_line]._obj, start, stop,
                                                               f"{value_str}") + END_LINE_TERM
            else:
                self.netlist[param_line] = _insert_section(self.netlist[param_line], start, stop,
                                                           f"{value_str}") + END_LINE_TERM
        else:
            # Was not found
            # the last two lines are typically (.backano and .end)
            insert_line = len(self.netlist) - 2
            term = Primitive(netlist=self, obj=f'.PARAM {param}={value_str}  ; Batch instruction' + END_LINE_TERM)
            self.netlist.insert(insert_line, term)

    def set_component_value(self, reference: str, value: Union[str, int, float]) -> None:
        """
        Changes the value of a component, such as a Resistor, Capacitor or Inductor.
        For components inside sub-circuits, use the sub-circuit designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            runner.set_component_value('R1', '3.3k')
            runner.set_component_value('X1:C1', '10u')

        :param reference: Reference of the circuit element to be updated.
        :type reference: str
        :param value:
            value to be set on the given circuit element. Float and integer values will be automatically
            formatted as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        self.get_component(reference).set_value(value)

    def set_element_model(self, reference: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            runner.set_element_model('D1', '1N4148')
            runner.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

        :param reference: Reference of the circuit element to be updated.
        :type reference: str
        :param model: model name of the device to be updated
        :type model: str

        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the model format contains irregular characters

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        super().set_element_model(reference, model)
        self.get_component(reference).set_value(model)

    def get_component_value(self, reference: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param reference: Reference of the circuit element to get the value.
        :type reference: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.get_component(reference).value_str

    def get_component_nodes(self, reference: str) -> list[str]:
        """
        Returns the nodes to which the component is attached to.

        :param reference: Reference of the circuit element to get the nodes.
        :type reference: str
        :return: List of nodes
        :rtype: list[str]
        """
        nodes = self.get_component(reference).ports
        return nodes

    def get_components(self, prefixes='*') -> list:
        """
        Returns a list of components that match the list of prefixes indicated on the parameter prefixes.
        In case prefixes is left empty, it returns all the ones that are defined by the REPLACE_REGEXES.
        The list will contain the designators of all components found.

        :param prefixes:
            Type of prefixes to search for. Examples: 'C' for capacitors; 'R' for Resistors; etc... See prefixes
            in SPICE documentation for more details.
            The default prefix is '*' which is a special case that returns all components.
        :type prefixes: str

        :return:
            A list of components matching the prefixes demanded.
        """
        answer = []
        if prefixes == '*':
            prefixes = ''.join(VALID_PREFIXES)
        for component in self.netlist:
            if isinstance(component, SpiceComponent):  # Only gets components from the main netlist,
                reference = component.reference
                try:
                    if reference[0] in prefixes:
                        answer.append(reference)  # Appends only the designators
                except IndexError or TypeError:
                    pass
        return answer

    def add_component(self, component: SpiceComponent, **kwargs) -> None:
        """
        Adds a component to the netlist. The component is added to the end of the netlist,
        just before the .END statement. If the component already exists, it will be replaced by the new one.

        :param component: The component to be added to the netlist
        :type component: Component
        :param kwargs:
            The following keyword arguments are supported:

            * **insert_before** (str) - The reference of the component before which the new component should be inserted.

            * **insert_after** (str) - The reference of the component after which the new component should be inserted.

        :return: Nothing
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        if 'insert_before' in kwargs:
            comp = self.get_component(kwargs['insert_before'])
            line_no = self.netlist.index(comp)
        elif 'insert_after' in kwargs:
            comp = self.get_component(kwargs['insert_after'])
            line_no = self.netlist.index(comp) + 1
        else:
            # Insert before backanno instruction
            try:
                line_no = self.netlist.index(
                    '.backanno\n')  # TODO: Improve this. END of line termination could be differnt
            except ValueError:
                line_no = len(self.netlist) - 2

        self.netlist.insert(line_no, component)
        super().add_component(component)

    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design. Current implementation only allows removal of a component
        from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        if self.is_read_only():
            raise ValueError("Editor is read-only")
        line = self.netlist.index(self.get_component(designator))
        del self.netlist[line]
        super().remove_component(designator)

    def get_all_nodes(self) -> list[str]:
        """
        Retrieves all nodes existing on a Netlist.

        :returns: Circuit Nodes
        :rtype: list[str]
        """
        circuit_nodes = []
        for line in self.netlist:
            prefix = get_line_command(line)
            if prefix in component_replace_regexs:
                match = component_replace_regexs[prefix].match(line)
                if match:
                    nodes = match.group('nodes').split()  # This separates by all space characters including \t
                    for node in nodes:
                        if node not in circuit_nodes:
                            circuit_nodes.append(node)
        return circuit_nodes

    def save_netlist(self, run_netlist_file: Union[str, Path, io.StringIO]) -> None:
        # docstring is in the parent class
        pass

    def class_for_instruction(self, instruction, cmd=""):
        if cmd == "":
            cmd = get_line_command(instruction)
        if cmd == ".CONTROL":
            # If it is a control instruction, then it should be added as a ControlEditor
            c = ControlEditor(self)
            c.content = instruction
            return c
        elif cmd in VALID_PREFIXES:
            # If it is a component, then it should be added as a SpiceComponent
            return SpiceComponent(netlist=self, obj=instruction)

        elif cmd.startswith('.'):
            # Otherwise, it is a Primitive
            return Primitive(netlist=self, obj=instruction)
        else:
            return instruction

    def add_instruction(self, instruction: str) -> None:
        # docstring in parent class
        cmd = get_line_command(instruction)
        if _is_unique_instruction(cmd):
            raise RuntimeError(f"Simulation directives like \"{cmd}\" can't be set on sub-circuits")
        if cmd == '.PARAM':
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')

        # check whether the instruction is already there (dummy proofing)
        for line in self.netlist:
            if isinstance(line, Primitive) and line._obj.strip() == instruction.strip():
                _logger.warning(
                    f'Instruction "{instruction.strip()}" is already present in the netlist. Ignoring addition.')
                return
        # TODO: if adding a .MODEL or .SUBCKT it should verify if it already exists and update it.

        if not instruction.endswith(END_LINE_TERM):
            instruction += END_LINE_TERM

        super().add_instruction(instruction)
        # Insert at the end
        primitive = self.class_for_instruction(instruction, cmd)
        line = len(self.netlist) - 1  # Just before the ENDS
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

    def is_read_only(self) -> bool:
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        if self.recording_updates:
            if self.parent:
                return self.parent.is_read_only()
            else:
                return True
        else:
            return False

    @property
    def top_netlist(self) -> BaseEditor:
        """Gets the custom lib path that is defined on the top netlist"""
        parent = self
        while (parent.netlist is not None):
            parent = parent.netlist
        assert isinstance(parent, BaseEditor)
        return parent

    @staticmethod
    def find_subckt_in_lib(library: str, subckt_name: str) -> Union['SpiceCircuit', None]:
        """
        Finds a sub-circuit in a library. The search is case-insensitive.

        :param library: path to the library to search
        :type library: str
        :param subckt_name: sub-circuit to search for
        :type subckt_name: str
        :return: Returns a SpiceCircuit instance with the sub-circuit found or None if not found
        :rtype: SpiceCircuit
        :meta private:
        """
        # 0. Setup things
        reg_subckt = re.compile(SUBCKT_CLAUSE_FIND + subckt_name, re.IGNORECASE)
        # 1. Find Encoding
        try:
            encoding = detect_encoding(library, r"[\* a-zA-Z]")
        except EncodingDetectError:
            return None
        #  2. scan the file
        with open(library, encoding=encoding) as lib:
            for line in lib:
                search = reg_subckt.match(line)
                if search:
                    sub_circuit = SpiceCircuit()
                    sub_circuit.netlist.append(Primitive(netlist=sub_circuit, obj=line))
                    # Advance to the next non nested .ENDS
                    finished = sub_circuit._add_lines(lib)
                    if finished:
                        # if this is from a lib, don't allow modifications
                        sub_circuit._readonly = True
                        return sub_circuit
        #  3. Return an instance of SpiceCircuit
        return None

    def find_subckt_in_included_libs(self, subcircuit_name: str) -> Optional["SpiceCircuit"]:
        """Find the subcircuit in the list of libraries

        :param subcircuit_name: sub-circuit to search for
        :type subcircuit_name: str
        :return: Returns a SpiceCircuit instance with the sub-circuit found or None if not found
        :rtype: SpiceCircuit
        :meta private:
        """
        for line in self.netlist:
            if isinstance(line, SpiceCircuit):  # If it is a sub-circuit it will simply ignore it.
                continue
            elif isinstance(line, ControlEditor):  # same for control editor
                continue
            m = lib_inc_regex.match(line)
            if m:  # If it is a library include
                lib = m.group(2)
                lib_filename = search_file_in_containers(lib,
                                                         os.path.split(self.top_netlist.circuit_file)[0],
                                                         # The directory where the file is located
                                                         os.path.curdir,  # The current script directory,
                                                         *self.simulator_lib_paths,  # The simulator's library paths
                                                         *self.top_netlist.custom_lib_paths)  # The custom library paths
                if lib_filename:
                    sub_circuit = self.find_subckt_in_lib(lib_filename, subcircuit_name)
                    if sub_circuit:
                        # Success we can go out
                        # by the way, this circuit will have been marked as readonly
                        return sub_circuit
        if self.parent is not None:
            # try searching on parent netlists
            return self.parent.find_subckt_in_included_libs(subcircuit_name)
        else:
            return None

    def modified_subcircuits(self) -> list['SpiceCircuit']:
        """
        Returns a list of all sub-circuits that have been modified.

        :return: List of modified sub-circuits
        :rtype: list[SpiceCircuit]
        """
        modified = []
        for subckt in self.netlist:
            if isinstance(subckt, SpiceCircuitInstance) and subckt.was_modified:
                modified.append(subckt.shadow_subcircuit)
            elif isinstance(subckt, SpiceCircuit) and subckt.was_modified:
                modified.append(subckt)
        return modified

class ControlEditor:
    """
    Provides interfaces to manipulate SPICE `.control` instructions.
    """

    def __init__(self, parent: SpiceCircuit = None):
        self._content = ""
        self.parent = parent

    def _add_lines(self, line_iter):
        """Internal function. Do not use.
        Add a list of lines to the section. No parsing, just loop until a .ENDC is found."""
        self._content = self._content.rstrip() + END_LINE_TERM
        for line in line_iter:
            self._content += line.rstrip() + END_LINE_TERM
            if line.strip().upper().startswith(".ENDC"):
                return True
        return False  # If a file ends abruptly, returns False

    def write_lines(self, f: io.StringIO):
        """Internal function. Do not use."""
        # This helper function writes the contents of the section to the file f
        f.write(self._content)

    @property
    def content(self) -> str:
        """The content as a string

        :getter: Returns the value as a string
        """
        return self._content

    @content.setter
    def content(self, value: str):
        """Sets the content of the ControlEditor to the given value.

        :param value: The new content to be set
        :type value: str
        """
        self._content = value.strip() + END_LINE_TERM