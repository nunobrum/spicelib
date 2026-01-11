from collections import OrderedDict
from math import floor, log
from typing import Union, List
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
        return "{:g}".format(value)  # This avoids a problematic log(0), and the int and float conversions
    e = floor(log(abs(value), 1000))
    if -5 <= e < 0:
        suffix = "fpnum"[e]
    elif e == 0:
        return "{:g}".format(value)
    elif e == 1:
        suffix = "k"
    elif e == 2:
        suffix = 'Meg'
    elif e == 3:
        suffix = 'g'
    elif e == 4:
        suffix = 't'
    else:
        return '{:E}'.format(value)
    return '{:g}{:}'.format(value * 1000 ** -e, suffix)


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
        # By industry convention, SPICE is not case sensitive
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


def to_float(value, accept_invalid: bool = True) -> Union[float, str]:
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

    def __init__(self, *args, **kwargs):
        self._netlist = kwargs.get('netlist', None)
        self.pointer = kwargs.get('pointer', None)
        self.name = ""
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
VALUE_IDs = ['value', 'val', 'v', 'value_str', 'model']
PARAMS_IDs = ['params', 'parameters', 'param']
REF_IDs = ['reference', 'ref', 'designator']


class Component(Primitive):
    """Holds component information"""
    default_netlist = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attributes = OrderedDict()
        self.ports : List[Net]= []
        self.reference = None

        self._netlist = self._netlist or self.default_netlist
        for i, arg in enumerate(args):
            if i == 0 and isinstance(arg, (int, float, str)):
                if isinstance(arg, str):
                    self.attributes['value_str'] = to_float(arg, accept_invalid=True)
                else:
                    self.attributes['value'] = arg
            elif isinstance(arg, Net):
                self.ports.append(arg)

        for key, value in kwargs.items():
            if key in  PORTS_IDs:
                self.ports = value
            elif key in PARAMS_IDs:
                self.attributes['params'] = value
            elif key in VALUE_IDs:
                self.attributes['value'] = to_float(value, accept_invalid=True)
            elif key in REF_IDs:
                self.reference = value


    def __hasattr__(self, item):
        if item in self.__dict__:
            return True
        if not self.__dict__.get('attributes'):
            return False
        attr_dict = self.__dict__['attributes']
        if item in attr_dict:
            return True
        elif item in VALUE_IDs:
            return 'value' in attr_dict
        elif item == 'model':
            return 'model' in attr_dict
        elif item in REF_IDs:
            return True
        elif item == 'parent' or item == '_parent':
            return True
        elif item in PORTS_IDs:
            return True
        elif item in PARAMS_IDs:
            return 'params' in attr_dict
        else:
            return False

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        attr_dict = self.__dict__.get('attributes', {})
        if item in VALUE_IDs:
            if 'value' not in attr_dict:
                raise ParameterNotFoundError(item)
            value = attr_dict['value']
            if item == 'value_str' and isinstance(value, (int, float)):
                return format_eng(value)
            elif item == 'value' and isinstance(value, str):
                return to_float(value, accept_invalid=True)
            else:
                return value
        elif item == 'model':
            if 'model' not in attr_dict:
                raise ParameterNotFoundError('model')
            return attr_dict['model']
        elif item in REF_IDs:
            if self.reference is None or self.reference == "":
                # self assigns to an attribute of the netlist?
                if self._netlist is not None:
                    for name, value in self._netlist.get_components().items():
                        if value is self:
                            self.reference = name
                            break
                else:
                    # Tries to find its name from locals
                    for name, value in locals().items():
                        if value is self:
                            self.reference = name
                            break

            return self.reference
        elif item == 'parent' or item == 'netlist':
            return self._netlist
        elif item in PORTS_IDs:
            return CallMe(self, Component.set_ports)
        elif item in PARAMS_IDs:
            return attr_dict.get('params', OrderedDict())
        elif item in attr_dict:
            return attr_dict[item]
        elif item in attr_dict.get('params', {}):
            return attr_dict['params'][item]
        else:
            return super().__getattribute__(item)

    def __setattr__(self, key, value):
        if key in VALUE_IDs:
            if self._netlist is None:
                raise ValueError("Component has no parent editor")
            if self._netlist.is_read_only():
                raise ValueError("Editor is read-only")
            if isinstance(value, (int, float)):
                value = format_eng(value)
            self.set_value(value)
        elif key in PARAMS_IDs:
            if self._netlist is None:
                raise ValueError("Component has no parent editor")
            if self._netlist.is_read_only():
                raise ValueError("Editor is read-only")
            self.set_parameters(**value)
        elif key in REF_IDs:
            super().__setattr__('reference', value)
        else:
            super().__setattr__(key, value)

    def set_ports(self, *args):
        """Sets the ports of the component
        :param args: List of Net objects
        """
        for arg in args:
            if not isinstance(arg, Net):
                arg = Net(arg)
            self.ports.append(arg)
        return self

    def __str__(self):
        return f"{self.reference} = {self.value}"

    def __getitem__(self, item):
        return self.__getattr__(item)

    def __setitem__(self, key, value):
        if key in VALUE_IDs:
            if isinstance(value, str):
                value = to_float(value, accept_invalid=True)
            self.attributes['value'] = value
            self.set_value(value)
        else:
            self.set_param(key, value)

    def set_value(self, value: Union[float, str]):
        """Sets the component value
        :param value: Component value
        """
        self.attributes['value'] = value

    def get_value(self) -> Union[float, str]:
        """Gets the component value
        :return: Component value
        """
        return self.attributes.get('value', float('nan'))

    def set_parameter(self, key: str, value: Union[float, str]):
        """Sets a parameter value
        :param key: Parameter name
        :param value: Parameter value
        """
        params = self.attributes.get('params', OrderedDict())
        if value is None:
            if key in params:
                del params[key]
        else:
            params[key] = value
        self.attributes['params'] = params

    def set_parameters(self, **params):
        """Sets multiple parameter values
        :param params: Dictionary with parameter names and values
        """
        current_params = self.attributes.get('params', OrderedDict())
        for key, value in params.items():
            if value is None:
                if key in current_params:
                    del current_params[key]
            else:
                current_params[key] = value
        self.attributes['params'] = current_params  # This instruction is only needed if params was empty before

    def clear_parameters(self):
        """Clears all parameters"""
        self.attributes['params'] = OrderedDict()

    def clear_paramemter(self, key: str):
        """Clears a parameter
        :param key: Parameter name
        """
        params = self.attributes.get('params', OrderedDict())
        if key in params:
            del params[key]
        self.attributes['params'] = params

    clear_param = clear_parameters
    set_param = set_parameter
    set_params = set_parameters

    def clone(self):
        """Clones the component"""
        newone = type(self)()
        newone._netlist = self._netlist
        newone._obj = copy.deepcopy(self._obj)
        newone.attributes = copy.deepcopy(self.attributes)
        newone.ports = self.ports.copy()
        newone.reference = self.reference
        return newone


if __name__ == "__main__":  # TODO: Delete this test code
    V = R = Component

    V1 = V(10).p('Vin', 'GND')
    print(R)

