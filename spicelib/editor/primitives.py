from collections import OrderedDict
from math import floor, log
import copy
from spicelib.editor.editor_errors import ParameterNotFoundError


def format_eng(value) -> str:
    """
    Helper function for formatting value with the SI qualifiers.  That is, it will use

        * p for pico (10E-12)
        * n for nano (10E-9)
        * u for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * Meg for Mega (10E+6)
        * g for giga (10E+9)
        * t for tera (10E+12)


    :param value: float value to format
    :type value: float
    :return: String with the formatted value
    :rtype: str
    """
    if value == 0.0:
        return f"{value:g}"  # This avoids a problematic log(0), and the int and float conversions
    e = floor(log(abs(value), 1000))
    if -5 <= e < 0:
        suffix = "fpnum"[e]
    elif e == 0:
        return f"{value:g}"
    elif e == 1:
        suffix = "k"
    elif e == 2:
        suffix = 'Meg'
    elif e == 3:
        suffix = 'g'
    elif e == 4:
        suffix = 't'
    else:
        return f'{value:E}'
    return f'{value * (1000 ** -e):g}{suffix}'


def scan_eng(value: str) -> float:
    """
    Converts a string to a float, considering SI multipliers

        * f for femto (10E-15)
        * p for pico (10E-12)
        * n for nano (10E-9)
        * u or µ for micro (10E-6)
        * m for mili (10E-3)
        * k for kilo (10E+3)
        * meg for Mega (10E+6)
        * g for giga (10E+9)
        * t for tera (10E+12)

    The extra unit qualifiers such as V for volts or F for Farads are ignored.


    :param value: string to be converted to float
    :type value: str
    :return:
    :rtype: float
    :raises: ValueError when the value cannot be converted.
    """
    # Search for the last digit on the string. Assuming that all after the last number are SI qualifiers and units.
    value = value.strip()
    x = len(value)
    while x > 0:
        if value[x - 1] in "0123456789":
            break
        x -= 1
    suffix = value[x:]  # this is the non-numeric part at the end
    f = float(value[:x])  # this is the numeric part. Can raise ValueError.
    if suffix:
        suffix = suffix.lower()
        # By industry convention, SPICE is not case-sensitive
        if suffix.startswith("meg"):
            return f * 1E+6
        elif suffix[0] in "fpnuµmkgt":
            return f * {
                'f': 1.0e-15,
                'p': 1.0e-12,
                'n': 1.0e-09,
                'u': 1.0e-06,
                'µ': 1.0e-06,
                'm': 1.0e-03,
                'k': 1.0e+03,
                'g': 1.0e+09,
                't': 1.0e+12,
            }[suffix[0]]
    return f


def to_float(value, accept_invalid: bool = True) -> float | str:
    _MULT = {
        'f': 1E-15,
        'p': 1E-12,
        'n': 1E-9,
        'µ': 1E-6,
        'u': 1E-6,
        'U': 1E-6,
        'm': 1E-3,
        'M': 1E-3,
        'k': 1E+3,
        'K': 1E+3,  # For much of the world, K is the same as k. That is a sad fact of life. K is Kelvin in SI
        'Meg': 1E+6,
        'g': 1E+9,
        't': 1E+12,
        # These units can be used as decimal points in the number definition. Ex: 10R5 is 10.5 Ohms. In LTSpice
        # the units can be used in any number definition. For example 10H5 is 10.5 Henrys but also can be used in
        # resistors value definition. LTSpice doesn't care about the unit in the component value definition.
        'Ω': 1,  # This is the Ohm symbol. It is supported by LTspice
        'R': 1,  # This also represents the Ohm symbol. Can be used a decimal point. Ex: 10R2 is 10.2 Ohms
        'V': 1,  # Volts
        'A': 1,  # Amperes (Current)
        'F': 1,  # Farads (Capacitance)
        'H': 1,  # Henry (Inductance)
        '%': 0.01,  # Percent. 10% is 0.1. 1%6 is 0.016
    }

    value = value.strip()  # Removing trailing and leading spaces
    length = len(value)

    multiplier = 1.0

    i = 0
    while i < length and (value[i] in "0123456789.+-"):  # Includes spaces
        i += 1
    if i == 0:
        if accept_invalid:
            return value
        else:
            raise ValueError("Doesn't start with a number")

    if 0 < i < length and (value[i] == 'E' or value[i] == 'e'):
        # if it is a number in scientific format, it doesn't have 1000x qualifiers (Ex: p, u, k, etc...)
        i += 1
        while i < length and (value[i] in "0123456789+-"):  # Includes spaces
            i += 1
        j = k = i
    else:
        # this first part should be able to be converted into float
        k = i  # Stores the position of the end of the number
        # Consume any spaces that may exist between the number and the unit
        while i < length and (value[i] in " \t"):
            i += 1

        if i < length:  # Still has characters to consume
            if value[i] in _MULT:
                if value[i:].upper().startswith('MEG'):  # to 1E+06 qualifier 'Meg'
                    i += 3
                    multiplier = _MULT['Meg']
                else:
                    multiplier = _MULT[value[i]]
                    i += 1

            # This part is done to support numbers with the format 1k7 or 1R8
            j = i
            while i < length and (value[i] in "0123456789"):
                i += 1
        else:
            j = i

    try:
        if j < i:  # There is a suffix number
            value = float(value[:k] + "." + value[j:i]) * multiplier
        else:
            value = float(value[:k]) * multiplier
    except ValueError as err:
        if not accept_invalid:
            raise err
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
        return str(getattr(self._netlist, self._obj, ''))

    def __iadd__(self, other):
        self._obj += other
        return self

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
        self._reference = None

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
            if key in  PORTS_IDs:
                self._set_ports(*value)  # This allows to set the ports with the "ports" keyword argument. Ex: R('R1', ports=['n1', 'n2'], value=10) or R('R1', p=['n1', 'n2'], value=10)
            elif key in PARAMS_IDs:
                self._attributes['params'] = value
            elif key in VALUE_IDs:
                self._attributes['value'] = to_float(value, accept_invalid=True)
            elif key in REF_IDs:
                self._reference = value

    @property
    def attributes(self):
        if not self._attributes:
            self.reset_attributes()
        return self._attributes

    @property
    def reference(self):
        if not self._reference:
            self.reset_attributes()
        return self._reference

    @reference.setter
    def reference(self, value):
        self._reference = value

    @property
    def parent(self):
        return self._netlist

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

    def port_names(self, sep=' '):
        """Gets the port names of the component
        :return: List of port names
        """
        if sep is None:
            return [port.name for port in self.ports]
        return sep.join(port.name for port in self.ports)

    @property
    def params(self):
        return self.get_parameters()

    @params.setter
    def params(self, params):
        self.set_parameters(**params)

    @property
    def value(self):
        return self.get_value()

    @value.setter
    def value(self, value):
        self.set_value(value)

    @property
    def value_str(self):
        return self.get_value_str()

    def _set_ports(self, ports):
        """Sets the ports of the component
        :param args: List of Net objects
        """
        self._attributes['ports'] = []
        for arg in ports:
            if isinstance(arg, Net):
                net = arg
                self._attributes['ports'].append(net)
            elif isinstance(arg, str):
                net = Net(arg, netlist=self._netlist)
                self._attributes['ports'].append(net)
            else:
                raise ValueError(f"Invalid port value: {arg}. Must be a string or a Net object.")
            net.nodes.append(self)

    def __str__(self):
        return f"{self.reference}({','.join(self.ports)}) = {self.value}"

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

    def set_value(self, value: float | int | str):
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

    def get_value(self) -> float | str | None:
        """
        :return: Component value
        """
        value = self.get_value_str()
        if isinstance(value, str):
            return to_float(value, accept_invalid=True)
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
            raise ParameterNotFoundError(f"Parameter '{key}' not found in component '{self.reference}'")

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

    ## Aliases for parameter functions
    def clear_param(self):
        self.clear_parameters()

    def set_param(self, key: str, value: float| str):
        self.set_parameter(key, value)

    def set_params(self, **params):
        self.set_parameters(**params)

    def clone(self, new_parent=None):
        """Clones the component"""
        newone = type(self)()
        newone._netlist = new_parent or self._netlist
        newone._obj = copy.deepcopy(self._obj)
        newone._attributes = copy.deepcopy(self._attributes)
        newone.reference = self.reference
        return newone

    def reset_attributes(self) -> dict:
        """Abstract function. Populates the attributes with the contents of the _obj attribute"""
        raise NotImplementedError(f"get_attributes not implemented in {self.__class__} class")

if __name__ == "__main__":  # TODO: Delete this test code
    V = R = Component

    V1 = V(10, ports=('Vin', 'GND'))
    print(R)

