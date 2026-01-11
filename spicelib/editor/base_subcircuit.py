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
# Name:        base_subcircuit.py
# Purpose:     Representation and parsing of SPICE subcircuits
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from abc import ABC, abstractmethod
from typing import Union

from spicelib.editor.primitives import Component, scan_eng
from .updates import UpdateType, Updates


class BaseSubCircuit(ABC):

    def __init__(self):
        """Initializing the list that contains all the modifications done to a netlist."""
        self.netlist_updates = Updates()
        self.recording_updates = False

    def add_update(self, name: str, value: Union[str, int, float, None], updates: UpdateType):
        if self.recording_updates:
            self.netlist_updates.add_update(name, value, updates)

    @abstractmethod
    def reset_netlist(self, create_blank: bool = False) -> None:
        ...

    @abstractmethod
    def get_component(self, reference: str) -> Component:
        """Returns the Component object representing the given reference in the netlist."""
        ...

    @abstractmethod
    def get_subcircuit(self, reference: str) -> 'BaseEditor':
        """Returns a hierarchical subdesign"""
        ...

    def __getitem__(self, item) -> Component:
        """
        This method allows the user to get the value of a component using the syntax:
        component = circuit['R1']
        """
        return self.get_component(item)

    def __setitem__(self, key, value):
        self.set_component_value(key, value)

    def get_component_attribute(self, reference: str, attribute: str) -> str:
        """
        Returns the value of the attribute of the component. Attributes are the values that are not related with
        SPICE parameters. For example, component manufacturer, footprint, schematic appearance, etc.
        User can define whatever attributes they want. The only restriction is that the attribute name must be a string.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute being sought
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the attribute is not found
        """
        return self.get_component(reference).attributes[attribute]

    def get_component_nodes(self, reference: str) -> list:
        """Returns the value of the port of the component.

        :param reference: Reference of the component
        :type reference: str
        :return: List with the ports of the component
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the port is not found

        """
        return self.get_component(reference).ports

    @abstractmethod
    def get_parameter(self, param: str) -> str:
        """
        Retrieves a Parameter from the Netlist

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """
        ...

    @abstractmethod
    def get_all_parameter_names(self) -> list[str]:
        """
        Returns all parameter names from the netlist.

        :return: A list of parameter names found in the netlist
        :rtype: list[str]
        """
        ...

    @abstractmethod
    def set_parameter(self, param, value):
        """Adds a parameter to the SPICE netlist.

        Usage: ::

         editor.set_parameter("TEMP", 80)

        This adds onto the netlist the following line: ::

         .PARAM TEMP=80

        This is an alternative to the set_parameters which is more pythonic in it's usage,
        and allows setting more than one parameter at once.

        :param param: Spice Parameter name to be added or updated.
        :type param: str

        :param value: Parameter Value to be set.
        :type value: str, int or float

        :return: Nothing
        """
        self.add_update(f'PARAM {param}', value, UpdateType.UpdateParameter)

    def set_parameters(self, **kwargs):
        """Adds one or more parameters to the netlist.
        Usage: ::

            for temp in (-40, 25, 125):
                for freq in sweep_log(1, 100E3,):
                    editor.set_parameters(TEMP=80, freq=freq)

        :key param_name:
            Key is the parameter to be set. values the ther corresponding values. Values can either be a str; an int or
            a float.

        :returns: Nothing
        """
        for param in kwargs:
            self.set_parameter(param, kwargs[param])

    @abstractmethod
    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        """Changes the value of a component, such as a Resistor, Capacitor or Inductor. For components inside
        sub-circuits, use the sub-circuit designator prefix with ':' as separator (Example X1:R1)
        Usage: ::

            editor.set_component_value('R1', '3.3k')
            editor.set_component_value('X1:C1', '10u')

        :param device: Reference of the circuit element to be updated.
        :type device: str
        :param value:
            value to be set on the given circuit element. Float and integer values will automatically
            formated as per the engineering notations 'k' for kilo, 'm', for mili and so on.
        :type value: str, int or float
        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the value doesn't correspond to the expected format

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this
            version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        self.add_update(device, value, UpdateType.UpdateComponentValue)

    @abstractmethod
    def set_element_model(self, element: str, model: str) -> None:
        """Changes the value of a circuit element, such as a diode model or a voltage supply.
        Usage: ::

            editor.set_element_model('D1', '1N4148')
            editor.set_element_model('V1' "SINE(0 1 3k 0 0 0)")

        :param element: Reference of the circuit element to be updated.
        :type element: str
        :param model: model name of the device to be updated
        :type model: str

        :raises:
            ComponentNotFoundError - In case the component is not found

            ValueError - In case the model format contains irregular characters

            NotImplementedError - In case the circuit element is defined in a format which is not supported by this version.

            If this is the case, use GitHub to start a ticket.  https://github.com/nunobrum/spicelib
        """
        self.add_update(element, model, UpdateType.UpdateComponentValue)

    @abstractmethod
    def set_component_parameters(self, element: str, **kwargs) -> None:
        """
        Adds one or more parameters to the component on the netlist. The argument is in the form of a key-value pair
        where each parameter is the key and the value is value to be set in the netlist.

        Usage 1: ::

         editor.set_component_parameters(R1, value=330, temp=25)

        Usage 2: ::

         value_settings = {'value': 330, 'temp': 25}
         editor.set_component_parameters(R1, **value_settings)

        :param element: Reference of the circuit element.
        :type element: str

        :key <param_name>:
            The key is the parameter name and the value is the value to be set. Values can either be
            strings; integers or floats. When None is given, the parameter will be removed, if possible.

        :return: Nothing
        :raises: ComponentNotFoundError - In case one of the component is not found.
        """
        for param, value in kwargs.items():
            update_type = UpdateType.DeleteComponentParameter if value is None else UpdateType.UpdateComponentParameter
            self.add_update(f"{element}:{param}", value, update_type)

    def set_component_attribute(self, reference: str, attribute: str, value: str) -> None:
        """Sets the value of the attribute of the component. Attributes are the values that are not related with
        SPICE parameters. For example, component manufacturer, footprint, schematic appearance, etc.
        User can define whatever attributes they want. The only restriction is that the attribute name must be a string.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be set
        :type attribute: str
        :param value: Value of the attribute to be set
        :type value: str
        :return: Nothing
        :raises: ComponentNotFoundError - In case the component is not found
        """
        self.add_update(reference, value, UpdateType.UpdateComponentParameter)
        self.get_component(reference).set_attribute(attribute, value)

    @abstractmethod
    def get_component_value(self, element: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value.
        :type element: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        ...

    @abstractmethod
    def get_component_parameters(self, element: str) -> dict:
        """
        Returns the parameters of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the parameters.
        :type element: str

        :return: parameters of the circuit element in dictionary format.
        :rtype: dict

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        ...

    def get_component_floatvalue(self, element: str) -> float:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value in float format.
        :type element: str

        :return: value of the circuit element in float type
        :rtype: float

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return scan_eng(self.get_component_value(element))

    def set_component_values(self, **kwargs):
        """
        Adds one or more components on the netlist. The argument is in the form of a key-value pair where each
        component designator is the key and the value is value to be set in the netlist.

        Usage 1: ::

         editor.set_component_values(R1=330, R2="3.3k", R3="1Meg", V1="PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)")

        Usage 2: ::

         value_settings = {'R1': 330, 'R2': '3.3k', 'R3': "1Meg", 'V1': 'PWL(0 1 30m 1 30.001m 0 60m 0 60.001m 1)'}
         editor.set_component_values(**value_settings)

        :key <comp_ref>:
            The key is the component designator (Ex: V1) and the value is the value to be set. Values can either be
            strings; integers or floats

        :return: Nothing
        :raises: ComponentNotFoundError - In case one of the component is not found.
        """
        for value in kwargs:
            self.set_component_value(value, kwargs[value])

    @abstractmethod
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
        ...

    @abstractmethod
    def add_component(self, component: Component, **kwargs) -> None:
        """
        Adds a component to the design. If the component already exists, it will be replaced by the new one.
        kwargs are implementation specific and can be used to pass additional information to the implementation.

        :param component: Component to be added to the design.
        :type component: Component

        :return: Nothing
        """
        value_or_model = component.value if component.value is not None else component.model
        self.add_update(component.reference, value_or_model, UpdateType.AddComponent)

    @abstractmethod
    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design.
        Note: Current implementation only allows removal of a component from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        self.add_update(designator, "delete", UpdateType.DeleteComponent)

    @abstractmethod
    def is_read_only(self):
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        ...

    @abstractmethod
    def add_instruction(self, instruction: str) -> None:
        """
        Adds a SPICE instruction to the netlist.

        For example:

            .. code-block:: text

                .tran 10m ; makes a transient simulation
                .meas TRAN Icurr AVG I(Rs1) TRIG time=1.5ms TARG time=2.5ms" ; Establishes a measuring
                .step run 1 100, 1 ; makes the simulation run 100 times

        :param instruction:
            Spice instruction to add to the netlist. This instruction will be added at the end of the netlist,
            typically just before the .BACKANNO statement
        :type instruction: str
        :return: Nothing
        """
        logtxt = instruction.strip().replace("\r", "\\r").replace("\n", "\\n")
        self.add_update("INSTRUCTION", logtxt, UpdateType.AddInstruction)

    @abstractmethod
    def remove_instruction(self, instruction: str) -> bool:
        """
        Removes a SPICE instruction from the netlist.

        Example:

        .. code-block:: python

            editor.remove_instruction(".STEP run -1 1023 1")

        This only works if the entire given instruction is contained in a line on the netlist.
        It uses the 'in' comparison, and is case sensitive.
        It will remove 1 instruction at most, even if more than one could be found.
        `remove_Xinstruction()` is a more flexible way to remove instructions from the netlist.

        :param instruction: The instruction to remove.
        :type instruction: str
        :returns: True if the instruction was found and removed, False otherwise
        :rtype: bool
        """
        logtxt = instruction.strip().replace("\r", "\\r").replace("\n", "\\n")
        self.add_update("INSTRUCTION", logtxt, UpdateType.DeleteInstruction)

    @abstractmethod
    def remove_Xinstruction(self, search_pattern: str) -> bool:
        """
        Removes a SPICE instruction from the netlist based on a search pattern. This is a more flexible way to remove
        instructions from the netlist. The search pattern is a regular expression that will be used to match the
        instructions to be removed. The search pattern is case insensitive, and will be applied to each line of the netlist.
        All matching lines will be removed.

        Example: The code below will remove all AC analysis instructions from the netlist.

        .. code-block:: python

            editor.remove_Xinstruction(r"\\.AC.*")

        :param search_pattern: Pattern for the instruction to remove. In general it is best to use a raw string (r).
        :type search_pattern: str
        :returns: True if the instruction was found and removed, False otherwise
        :rtype: bool
        """
        ...

    def add_instructions(self, *instructions) -> None:
        """
        Adds a list of instructions to the SPICE NETLIST.

        Example:

        .. code-block:: python

            editor.add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")

        :param instructions: Argument list of instructions to add
        :type instructions: argument list
        :returns: Nothing
        """

        for instruction in instructions:
            self.add_instruction(instruction)


class BaseSubCircuitInstance(BaseSubCircuit):
    @property
    @abstractmethod
    def subcircuit(self) -> BaseSubCircuit:
        """Returns the subcircuit object representing this instance."""
        ...

    def get_component(self, reference: str) -> Component:
        """Returns the Component object representing the given reference in the netlist."""
        return self.subcircuit.get_component(reference)

    def get_subcircuit(self, reference: str) -> BaseSubCircuit:
        """Returns a hierarchical subdesign"""
        return self.subcircuit.get_subcircuit(reference)

    def get_component_attribute(self, reference: str, attribute: str) -> str:
        """
        Returns the value of the attribute of the component. Attributes are the values that are not related with
        SPICE parameters. For example, component manufacturer, footprint, schematic appearance, etc.
        User can define whatever attributes they want. The only restriction is that the attribute name must be a string.

        :param reference: Reference of the component
        :type reference: str
        :param attribute: Name of the attribute to be retrieved
        :type attribute: str
        :return: Value of the attribute being sought
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the attribute is not found
        """
        return self.subcircuit.get_component_attribute(reference, attribute)

    def get_component_nodes(self, reference: str) -> list:
        """Returns the value of the port of the component.

        :param reference: Reference of the component
        :type reference: str
        :return: List with the ports of the component
        :rtype: str
        :raises: ComponentNotFoundError - In case the component is not found
                 KeyError - In case the port is not found

        """
        return self.subcircuit.get_component_nodes(reference)

    def get_parameter(self, param: str) -> str:
        """
        Retrieves a Parameter from the Netlist

        :param param: Name of the parameter to be retrieved
        :type param: str
        :return: Value of the parameter being sought
        :rtype: str
        :raises: ParameterNotFoundError - In case the component is not found
        """
        return self.subcircuit.get_parameter(param)

    def get_all_parameter_names(self) -> list[str]:
        """
        Returns all parameter names from the netlist.

        :return: A list of parameter names found in the netlist
        :rtype: list[str]
        """
        return self.subcircuit.get_all_parameter_names()

    def get_component_value(self, element: str) -> str:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value.
        :type element: str

        :return: value of the circuit element .
        :rtype: str

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.subcircuit.get_component_value(element)

    def get_component_parameters(self, element: str) -> dict:
        """
        Returns the parameters of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the parameters.
        :type element: str

        :return: parameters of the circuit element in dictionary format.
        :rtype: dict

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.subcircuit.get_component_parameters(element)

    def get_component_floatvalue(self, element: str) -> float:
        """
        Returns the value of a component retrieved from the netlist.

        :param element: Reference of the circuit element to get the value in float format.
        :type element: str

        :return: value of the circuit element in float type
        :rtype: float

        :raises: ComponentNotFoundError - In case the component is not found

                 NotImplementedError - for not supported operations
        """
        return self.subcircuit.get_component_floatvalue(element)

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
        return self.subcircuit.get_components(prefixes)
