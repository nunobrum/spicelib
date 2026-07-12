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
# License:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import io
import logging
import re

from .base_editor import BaseEditor
from .base_subcircuit import BaseSubCircuitInstance, BaseSubCircuit
from .primitives import VALUE_IDs, PARAMS_IDs, Component, ValueType
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
        super().reset_attributes()
        # The instruction below might fail if the sub-circuit was not parsed in the parent netlist.
        self._subcircuit = self._netlist.get_subcircuit_named(self.value)  # In case it isn't given, get it from the parent

    @property
    def subcircuit(self):
        """Makes a copy of the target sub-circuit in order to manage updates done to instances. This is only
        saved if there is an update made to it."""
        if self._subcircuit is None:
            # Try to get it from the parent netlist
            self._subcircuit = self._netlist.get_subcircuit_named(self.value) # pyright: ignore[reportOptionalMemberAccess]
            if self._subcircuit is None:
                raise AssertionError(f"Couldn't find the subcircuit named \"{self.value}\"")
            self.shadow_subcircuit = None
        if self.shadow_subcircuit is None:
            # In all cases it creates a new copy of the subcircuit, it is only writen to the netlist if it was modified.
            new_name = self.value_str + '_' + self.reference
            self.shadow_subcircuit = self._subcircuit.clone(self, new_name=new_name)
        return self.shadow_subcircuit

    def get_subcircuit_named(self, name: str) -> BaseSubCircuit | None:
        """Returns the sub-circuit instance with the given name. This is used to get the sub-circuit instance of a sub-circuit instance."""
        if self.parent:
            return self.parent.get_subcircuit_named(name)
        else:
            return None

    def set_value(self, value):
        """Makes sure the copies are invalidated"""
        super().set_value(value)
        self._subcircuit = None
        self.shadow_subcircuit = None

    @property
    def was_modified(self):
        """Returns True if the sub-circuit was modified, False otherwise."""
        return self.shadow_subcircuit is not None and self.shadow_subcircuit._modified

    def begin_update(self) -> UpdatePermission:
        netlist: BaseSubCircuit = self._netlist # pyright: ignore[reportAssignmentType]
        permission = netlist.begin_update()
        if permission == UpdatePermission.Inform and self.was_modified is False:
            # First update => Also update the subcircuit
            if permission == UpdatePermission.Inform:
                old_name = self.value_str
                netlist.end_update(f'CLONE({old_name})', old_name, UpdateType.CloneSubcircuit)
                name = self.subcircuit.name()
                Component.set_value(self, name)  # Jumps the update tracking
                netlist.end_update(self.reference, name, UpdateType.UpdateComponentValue)
        return permission

    def end_update(self, name: str, value: ValueType | None, updates: UpdateType):
        # Make sure the modification is registered
        self.shadow_subcircuit._modified = True
        # Redirect the update to the parent
        netlist: BaseSubCircuit = self._netlist # pyright: ignore[reportAssignmentType]
        netlist.end_update(f"{self.reference}:{name}", value, updates)

    def reset_netlist(self, **kwargs) -> bool:
        self.shadow_subcircuit = None
        return True

    def __setattr__(self, key, value):
        if key in VALUE_IDs:
            self.set_value(value)
        elif key in PARAMS_IDs:
            self.set_parameters(**value)
        else:
            SpiceComponent.__setattr__(self, key, value)

    def __getitem__(self, item) -> SpiceComponent | ValueType:
        """
       This returns a component or a parameter of the subcircuit using the syntax:
       circuit['R1']  # returns the component R1
       circuit['TEMP']  # returns the parameter TEMP
       In case the item is not found as a component, it will try to get it as a parameter.
        """
        if item in VALUE_IDs or item in PARAMS_IDs:
            return getattr(self, item)
        elif item in self.get_components():
            return self.get_component(item) # pyright: ignore[reportReturnType]
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
            self.set_component_value(key, value)
        elif key in self.subcircuit.get_all_parameter_names():
            self.set_parameter(key, value)
        else:
            raise KeyError(f'Key "{key}" not found as component or parameter in subcircuit "{self.reference}".')


    def set_component_value(self, device: str, value: ValueType) -> None:
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
        logger.debug(f'Setting component "{device}" to value "{value}"')
        component = self.get_component(device)
        component.set_value(value)

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
        component = self.get_component(element)
        component.set_value(model)

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
        self.get_component(element).set_parameters(**kwargs)

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
        component  = self.get_component(reference)
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
                self.end_update(device, value, UpdateType.UpdateComponentValue)


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
