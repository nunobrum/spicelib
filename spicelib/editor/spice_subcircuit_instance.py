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
# Purpose:     Used to edit SPICE netlists and keep track of updated elements
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import io
from typing import Union
import logging
import re

from .base_editor import BaseEditor
from .base_subcircuit import BaseSubCircuitInstance, BaseSubCircuit
from .primitives import VALUE_IDs, PARAMS_IDs, Component
from .updates import UpdateType, UpdatePermission
from .spice_components import SpiceComponent, component_replace_regexs, _parse_params, undress_designator

logger = logging.getLogger("spicelib.SpiceEditor")

class SpiceCircuitInstance(SpiceComponent, BaseSubCircuitInstance):
    """Used for object-oriented manipulations where the parent reference of a component needs to be
    stored for registering updates, and managing modified sub-circuits.

    This class only implements
    """

    def __init__(self, *ars, **kwargs):
        SpiceComponent.__init__(self, *ars, **kwargs)
        self._subcircuit = None
        self.shadow_subcircuit = None

    def reset_attributes(self):
        """Resets the sub-circuit instance to its original state."""
        new_line = re.sub(r'[\n\r]+\s*', ' ', self._obj)  # cleans up line breaks and extra spaces and tabs
        regex = component_replace_regexs['X']
        match: re.Match = regex.match(new_line)
        self._attributes.clear()
        ref = match.group('designator')
        self._reference = undress_designator(ref)
        self._set_ports(match.group('nodes').strip().split())
        self._attributes['value'] =match.group('value').strip()
        if match.group('params'):
            self._attributes['params'] = _parse_params(match.group('params'))
        # The instruction below might fail if the sub-circuit was not parsed in the parent netlist.
        self._subcircuit = self._netlist.get_subcircuit_named(self.value)  # In case it isn't given, get it from the parent

    def write_lines(self, stream: io.StringIO) -> int:
        """If the subcircuit was modified it needs to update the reference to the subcircuit"""
        if self.was_modified:
            self.value = self.shadow_subcircuit.name()  # needed so that the instance is named with the new name
        return super().write_lines(stream)

    @property
    def subcircuit(self):
        """Makes a copy of the target sub-circuit in order to manage updates done to instances. This is only
        saved if there is an update made to it."""
        if self._subcircuit is None:
            # Try to get it from the parent netlist
            self._subcircuit = self._netlist.get_subcircuit_named(self.value)
            if self._subcircuit is None:
                raise AssertionError(f"Couldn't find the subcircuit named \"{self.value}\"")
            self.shadow_subcircuit = None
        if self.shadow_subcircuit is None:
            # In all cases it creates a new copy of the subcircuit, it is only writen to the netlist if it was modified.
            new_name = self.value + '_' + self.reference
            self.shadow_subcircuit = self._subcircuit.clone(self, new_name=new_name)
        return self.shadow_subcircuit

    def get_subcircuit_named(self, name: str) -> BaseSubCircuit | None:
        """Returns the sub-circuit instance with the given name. This is used to get the sub-circuit instance of a sub-circuit instance."""
        if self.parent:
            return self.parent.get_subcircuit_named(name)
        else:
            return None

    @property
    def was_modified(self):
        """Returns True if the sub-circuit was modified, False otherwise."""
        return self.shadow_subcircuit is not None and self.shadow_subcircuit.was_modified

    def begin_update(self) -> UpdatePermission:
        permission = self._netlist.begin_update()
        if permission == UpdatePermission.Inform and self.was_modified is False:
            # First update => Also update the subcircuit
            if permission == UpdatePermission.Inform:
                old_name = self.value
                self._netlist.end_update(f'CLONE({old_name})', old_name, UpdateType.CloneSubcircuit)
                name = self.subcircuit.name()
                Component.set_value(self, name)  # Jumps the update tracking
                self._netlist.end_update(self.reference, name, UpdateType.UpdateComponentValue)
        return permission

    def end_update(self, name: str, value: Union[str, int, float, None], updates: UpdateType):
        # Make sure the modification is registered
        self.shadow_subcircuit._modified = True
        # Redirect the update to the parent
        self._netlist.end_update(f"{self.reference}:{name}", value, updates)

    def reset_netlist(self, create_blank: bool = False) -> None:
        self.shadow_subcircuit = None

    def __setattr__(self, key, value):
        if key in VALUE_IDs:
            self.set_value(value)
        elif key in PARAMS_IDs:
            self.set_parameters(**value)
        else:
            super().__setattr__(key, value)

    def __getitem__(self, item) -> Union[SpiceComponent, str]:
        """
       This returns a component or a parameter of the subcircuit using the syntax:
       circuit['R1']  # returns the component R1
       circuit['TEMP']  # returns the parameter TEMP
       In case the item is not found as a component, it will try to get it as a parameter.
        """
        if item in VALUE_IDs or item in PARAMS_IDs:
            return getattr(self, item)
        elif item in self.get_components():
            return self.get_component(item)
        elif item in self.get_all_parameter_names():
            return self.get_parameter(item)
        else:
            raise KeyError(f'Key "{item}" not found as component or parameter in subcircuit "{self.value}".')


    def __setitem__(self, key, value):
        """
        This method allows the user to set the value of a component using the syntax:
        circuit['R1'] = '3.3k'
        If the key is not found, and if there is a parameter with the same name, it will set the parameter value instead.
        """
        if key in self.subcircuit.get_components():
            self.set_component_attribute(key, 'value', value)
        elif key in self.subcircuit.get_all_parameter_names():
            self.set_parameter(key, value)
        else:
            raise KeyError(f'Key "{key}" not found as component or parameter in subcircuit "{self.reference}".')


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
        if p := self.begin_update() == UpdatePermission.Deny:
            logger.warning(f'Parameter "{param}" is already set to "Deny".')
            return
        logger.debug(f'Setting parameter "{param}" to value "{value}"')
        SpiceComponent.set_parameter(self, param, value)

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
        self.begin_update()
        logger.debug(f'Setting parameters: {kwargs}')
        SpiceComponent.set_parameters(self, **kwargs)

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
        self.begin_update()
        logger.debug(f'Setting component "{device}" to value "{value}"')
        self.get_component(device).set_component(value)

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
        self.begin_update()
        logger.debug(f'Setting element "{element}" to model "{model}"')
        self.get_component(element).set_component(model)

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
        self.begin_update()
        logger.debug(f'Setting parameters for component "{element}": {kwargs}')
        self.get_component(element).set_component_parameters(**kwargs)

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
        self.begin_update()
        logger.debug(f'Setting attribute "{attribute}" of component "{reference}" to value "{value}"')
        component  = self.get_component(reference).set_component(attribute, value)
        setattr(component, attribute, value)
        # self.end_update(reference, value, UpdateType.UpdateComponentParameter)


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
        permission = self.begin_update()
        if permission == UpdatePermission.Deny:
            raise ValueError("Editor is read-only")
        self.subcircuit.set_component_values(**kwargs)
        if permission == UpdatePermission.Inform:
            for device, value in kwargs.items():
                self.add_update(device, value, UpdateType.UpdateComponentValue)


    def add_component(self, component: SpiceComponent, **kwargs) -> None:
        """
        Adds a component to the design. If the component already exists, it will be replaced by the new one.
        kwargs are implementation specific and can be used to pass additional information to the implementation.

        :param component: Component to be added to the design.
        :type component: Component

        :return: Nothing
        """
        self.begin_update()
        self.subcircuit.add_component(component, **kwargs)

    def remove_component(self, designator: str) -> None:
        """
        Removes a component from  the design.
        Note: Current implementation only allows removal of a component from the main netlist, not from a sub-circuit.

        :param designator: Component reference in the design. Ex: V1, C1, R1, etc...
        :type designator: str

        :return: Nothing
        :raises: ComponentNotFoundError - When the component doesn't exist on the netlist.
        """
        self.begin_update()
        self.subcircuit.remove_component(designator)

    def is_read_only(self):
        """Check if the component can be edited. This is useful when the editor is used on non modifiable files.

        :return: True if the component is read-only, False otherwise
        :rtype: bool
        """
        return self.editor is None or self.editor.is_read_only()
