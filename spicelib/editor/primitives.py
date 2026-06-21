from collections import OrderedDict
import copy
from typing import TypeAlias
from .editor_errors import ParameterNotFoundError
from ..utils.float_unit import format_eng, scan_eng, to_float, float_unit


ValueType: TypeAlias = str | float | int | complex



def try_value(token: str) -> ValueType:
    """Try to convert a token to an int or float, if it fails return the original string"""
    try:
        value = to_float(token, accept_invalid=False)
    except ValueError as err:
        try:
            return complex(token)
        except ValueError:
            return token
    else:
        return value


class CallMe(object):
    """Used to create callable objects to set properties back on the parent object"""

    def __init__(self, parent, func):
        self._parent = parent
        self.func = func

    def __call__(self, *args, **kwargs):
        self.func(self._parent, *args, **kwargs)
        return self._parent


class Net(object):
    """Holds net information"""

    def __init__(self, name, **kwargs):
        self._netlist = kwargs.get('netlist', None)
        self.name = name
        self.nodes = []

    def __str__(self):
        return self.name

    def __call__(self, *args):
        for arg in args:
            if isinstance(arg, str):
                self.nodes.append(arg)
        return self


class Primitive(object):
    """Holds the information of a primitive element in the netlist. This is a base class for the Component and is
    used to hold the information of the netlist primitives, such as .PARAM, .OPTIONS, .IC, .NODESET, .GLOBAL, etc.
    """

    def __init__(self, *args, **kwargs):
        self._netlist = kwargs.get('netlist', None)
        self._obj = kwargs.get('obj', None)

    def __str__(self):
        return str(self._obj)

    def __iadd__(self, other):
        self._obj += other
        return self

    @property
    def obj(self):
        return self._obj
    
    @property
    def parent(self):
        return self._netlist


PORTS_IDs = ['ports', 'p', 'pins']
VALUE_IDs = ['value', 'val', 'v', 'value_str', 'model', 'Value']
PARAMS_IDs = ['params', 'parameters', 'param']
REF_IDs = ['reference', 'ref', 'designator']


class Component(Primitive):
    """Holds component information"""
    default_netlist = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attributes = {}
        self._reference = ''

        self._netlist = self._netlist or self.default_netlist  # This allows to create components without specifying the netlist every time
        for i, arg in enumerate(args):
            if i == 0 and isinstance(arg, (int, float, str)):
                if isinstance(arg, str):
                    self._attributes['value_str'] = to_float(arg, accept_invalid=True)
                else:
                    self._attributes['value'] = arg
            elif isinstance(arg, Net):
                self.ports.append(arg)

        for key, value in kwargs.items():
            if key in PORTS_IDs:
                self._set_ports(value)  # This allows to set the ports with the "ports" keyword argument. Ex: R('R1', ports=['n1', 'n2'], value=10) or R('R1', p=['n1', 'n2'], value=10)
            elif key in PARAMS_IDs:
                self._attributes['params'] = value
            elif key in VALUE_IDs:
                self._attributes['value'] = to_float(value, accept_invalid=True)
            elif key in REF_IDs:
                self._reference = value

    @property
    def attributes(self) -> dict:
        if not self._attributes:
            self.reset_attributes()
        return self._attributes

    @property
    def reference(self) -> str:
        if not self._reference:
            self.reset_attributes()
        return self._reference

    @reference.setter
    def reference(self, value):
        self._reference = value

    @property
    def ports(self) -> list[Net]:
        """Gets the ports of the component
        :return: List of Net objects
        """
        if 'ports' in self.attributes:
            return self._attributes['ports']
        else:
            return []

    @ports.setter
    def ports(self, value):
        self._set_ports(value)

    def port_names(self, sep=' ') ->  str:
        """Gets the port names of the component
        :return: List of port names
        """
        return sep.join(port.name for port in self.ports)
    
    def port_list(self) -> list[str]:
        """Gets the port names of the component as a list
        :return: List of port names
        """
        return [port.name for port in self.ports]

    @property
    def params(self) -> OrderedDict:
        return self.get_parameters()

    @params.setter
    def params(self, params: dict):
        self.set_parameters(**params)

    @property
    def value(self):
        return self.get_value()

    @value.setter
    def value(self, value):
        self.set_value(value)

    @property
    def value_str(self) -> str | None:
        return self.get_value_str()
    
    @value_str.setter
    def value_str(self, value):
        self.set_value(value)

    def _set_ports(self, ports: list[Net] | list[str]):
        """Sets the ports of the component
        :param ports: List of Net objects or strings representing the ports. Ex: ['n1', 'n2'] or [Net('n1'), Net('n2')]
        """
        ports_list  = []
        for arg in ports:
            if isinstance(arg, Net):
                net = arg
                ports_list.append(net)
            elif isinstance(arg, str):
                net = Net(arg, netlist=self._netlist)
                ports_list.append(net)
            else:
                raise ValueError(f"Invalid port value: {arg}. Must be a string or a Net object.")
            net.nodes.append(self)
        self._attributes['ports'] = ports_list

    def __str__(self):
        return self._obj or self._reference

    def __getitem__(self, item):
        if item in VALUE_IDs:
            return self.get_value()
        else:
            try:
                return self.get_parameter(item)
            except IndexError:
                pass

    def __setitem__(self, key, value):
        if key in VALUE_IDs:
            if isinstance(value, str):
                value = to_float(value, accept_invalid=True)
            self.attributes['value'] = value
        else:
            self.set_parameter(key, value)

    def set_value(self, value: ValueType):
        """
        :param value: Component value to set
        """
        self.attributes['value'] = value

    def get_value_str(self) -> str | None:
        """
        :return: Component value in string format
        """
        value = self.attributes.get('value')
        if isinstance(value, (int, float)):
            return format_eng(value)
        return value

    def get_value(self) -> ValueType | str | None:
        """
        :return: Component value
        """
        value = self.get_value_str()
        if isinstance(value, str):
            value = try_value(value)
        return value

    def get_parameters(self) -> OrderedDict:
        """Gets all parameter values
        :return: Dictionary with parameter names and values
        """
        if 'params' in self.attributes:
            return self._attributes['params']
        else:
            return OrderedDict()

    def get_parameter(self, key: str) -> float | str:
        """Gets a parameter value
        :param key: Parameter name
        :return: Parameter value
        :raises: ParameterNotFoundError when the parameter is not found
        """
        params = self.get_parameters()
        if key in params:
            return params[key]
        else:
            raise ParameterNotFoundError(key, f"component '{self.reference}'")

    def set_parameter(self, key: str, value: float | str):
        """Sets a parameter value
        :param key: Parameter name
        :param value: Parameter value
        """
        params = self.get_parameters()
        if value is None:
            if key in params:
                del params[key]
        else:
            params[key] = value
        self._attributes['params'] = params

    def set_parameters(self, **params):
        """Sets multiple parameter values
        :param params: Dictionary with parameter names and values
        """
        self.attributes['params'] = params  # This instruction is only needed if params was empty before

    def clear_parameters(self):
        """Clears all parameters. It will set all existing parameters to None. This will delete them when writing
        back to file."""
        params = self.get_parameters()
        if params:
            for key in params:
                params[key] = None

    def clear_parameter(self, key: str):
        """Clears a parameter.
        :param key:  name
        """
        if 'params' not in self._attributes:
            self._attributes['params'] = OrderedDict()
        self._attributes['params'][key] = None

    # Aliases for parameter functions
    def clear_param(self):
        self.clear_parameters()

    def set_param(self, key: str, value: float | str):
        self.set_parameter(key, value)

    def set_params(self, **params):
        self.set_parameters(**params)

    def clone(self, new_parent=None):
        """Clones the component"""
        newone = type(self)()
        newone._netlist = new_parent or self._netlist
        newone._obj = copy.deepcopy(self._obj)
        newone._attributes = copy.deepcopy(self._attributes)
        newone._reference = self._reference
        return newone

    def reset_attributes(self) -> dict:
        """Abstract function. Populates the attributes with the contents of the _obj attribute"""
        raise NotImplementedError(f"get_attributes not implemented in {self.__class__} class")


if __name__ == "__main__":  # TODO: Delete this test code
    V = R = Component

    V1 = V(10, ports=('Vin', 'GND'))
    print(R)
