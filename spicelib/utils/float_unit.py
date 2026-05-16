# -*- coding: utf-8 -*-
"""
Scanning and Formatting of constants in Equations
"""
import math


def format_eng(value: float | int) -> str:
    """
    Format value with engineering SI qualifiers.

    If ``value`` is a ``float_unit`` instance, the stored unit is preserved.
    """
    if value == 0.0:
        return f"{value:g}"

    exp = math.floor(math.log(abs(value), 1000))
    if exp == 0:
        return f"{value:g}"
    elif -5 <= exp < 0:
        suffix = "fpnum"[exp]
    elif exp == 1:
        suffix = 'k'
    elif exp == 2:
        suffix = 'Meg'
    elif exp == 3:
        suffix = 'g'
    elif exp == 4:
        suffix = 't'
    else:
        return f"{value:E}"

    return f"{value * (1000 ** -exp):g}{suffix}"


def parse_value(value, accept_invalid):
    unit = ''
    try:
        value = value.strip()  # Removing trailing and leading spaces
        l = len(value)

        if l == 0:
            raise ValueError('Received empty string')
        multiplier = 1.0
        suffix_number = ''
        i = 0
        while i < l and (value[i] in "0123456789.+-"):  # Includes spaces
            i += 1
        if i == 0:
            if not accept_invalid:
                raise ValueError("Doesn't start with a number")
        elif 0 < i < l and value[i].upper() == 'E':
            # if it is a number in scientific format, it doesn't have 1000x qualifiers (Ex: p, u, k, etc...)
            i += 1
            while i < l and (value[i] in "0123456789E+-"):  # Includes spaces
                i += 1
            k = i
        else:
            # this first part should be able to be converted into float
            k = i  # Stores the position of the end of the number
            # Consume any spaces that may exist
            while i < l and (value[i] in " \t"):
                i += 1

            if i < l:  # Still has characters to consume
                if value[i] in _MULT:
                    multiplier = _MULT[value[i]]
                    if value[i:].upper().startswith('MEG'):  # to support Spice like qualifier 'MEG'
                        i += 3
                    else:
                        i += 1
                elif value[i].upper() == 'R':  # This supports the format 4R7
                    i += 1
                    unit = 'Ω'

                # This part is done to support numbers with the format 1k7 or 1R8
                j = i
                while i < l and (value[i] in "0123456789"):
                    i += 1
                suffix_number = value[j:i]

        # Consume any spaces that may exist
        while i < l and (value[i] in " \t"):
            i += 1
        if i < l:
            unit = value[i:]

        if suffix_number:
            value = float(value[:k] + "." + suffix_number) * multiplier
        else:
            value = float(value[:k]) * multiplier

        value = int(value) if value.is_integer() else value

    except (ValueError, UnitError) as err:
        if accept_invalid:
            value = math.nan
        else:
            raise err
    return value, unit


def scan_eng(value: str) -> float:
    """
    Convert a string to float while honoring engineering multipliers.

    Extra trailing unit qualifiers (for example ``V`` or ``F``) are ignored.
    """
    value, _ = parse_value(value, accept_invalid=False)
    return value


class UnitError(Exception):
    """Class used to invalidate errors with units"""
    

class Unit(object):
    one_name = ''
    many_name = ''
    sign = ''

    def __str__(self):
        return self.sign

    def __repr__(self):
        return self.sign


class Ohm(Unit):
    one_name = "Ohm"
    many_name = "Ohms"
    sign = 'Ω'


class Volt(Unit):
    one_name = "Volt"
    many_name = "Volts"
    sign = 'V'


class Ampere(Unit):
    one_name = "Ampere"
    many_name = "Amperes"
    sign = 'A'


class Farad(Unit):
    one_name = "Farad"
    many_name = "Farads"
    sign = 'F'


class Henry(Unit):
    one_name = "Henry"
    many_name = "Henries"
    sign = 'H'


class Watt(Unit):
    one_name = "Watt"
    many_name = "Watts"
    sign = 'W'


class Coulombs(Unit):
    one_name = "Coulom"
    many_name = "Coulombs"
    sign = 'C'


class Joules(Unit):
    one_name = "Joule"
    many_name ="Joules"
    sign = 'J'

class Celsius(Unit):
    one_name = "Celsius"
    many_name ="Celsius"
    sign = '°C'

class Kelvin(Unit):
    one_name = "Kelvin"
    many_name ="Kelvins"
    sign = 'K'


class Hertz(Unit):
    one_name = "Hertz"
    many_name ="Hertz"
    sign = 'Hz'


class seconds(Unit):
    one_name = "second"
    many_name ="seconds"
    sign = 's'


class Percent(Unit):  # TODO: Make operations with %
    one_name = "percent"
    many_name = "percent"
    sign = "%"


class PPM(Unit):  # TODO: Make operations with ppm
    one_name = "ppm"
    many_name = "ppm"
    sign = "ppm"


class Degrees(Unit):
    one_name = 'Degree'
    many_name = 'Degrees'
    sign = '°'


class Radians(Unit):
    one_name = 'radians'
    many_name = 'radians'
    sign = 'rad'


class Vrms(Unit):
    one_name = 'Vrms'
    many_name = 'Vrms'
    sign = 'Vrms'


class Arms(Unit):
    one_name = 'Vrms'
    many_name = 'Vrms'
    sign = 'Vrms'

_MULT = {
    'f': 1E-15,
    'p': 1E-12,
    'P': 1E-12,
    'n': 1E-9,
    'N': 1E-9,
    'u': 1E-6,
    'µ': 1E-6,
    'μ': 1E-6,
    'U': 1E-6,
    'm': 1E-3,  # This is the only qualifier where the case is important
    'k': 1E+3,
    'K': 1E+3,
    'M': 1E+6,
    'G': 1E+9,
    'g': 1E+9,
    'T': 1E+12,
    't': 1E+12,
    '%': 1E-2,
}

_UNITS = {
    'R': Ohm,
    'Ω': Ohm,
    'V': Volt,
    'A': Ampere,
    'F': Farad,
    'H': Henry,
    'W': Watt,
    'C': Coulombs,
    'J': Joules,
    # 'S': Siemens,
    's': seconds,
    'K': Kelvin,
    'Hz': Hertz,
    '%': Percent,
    '°C': Celsius,
    'DEG': Degrees,  # Used by Tektronix Signal Generator
    'RAD': Radians,
    'ARMS': Arms,  # Used by Fluke Multimeter
    'VRMS': Vrms,  # Used by Fluke Multimeter
}


class float_unit(float):
    """
    A class which represents a floating point number with an associated physical unit.
    """

    def __init__(self, value, unit=''):
        super().__init__()
        self._original = None
        if isinstance(value, str):
            self._original = value.strip()
            value, unit0 = parse_value(value, accept_invalid=False)
            if unit0 != '':
                if unit != '' and unit != unit0:
                    raise RuntimeError("Unit missmatch")
                unit = unit0
        else:
            unit = unit

        if unit in _UNITS:
            self._unit = _UNITS[unit]
        else:
            self._unit = Unit

    def __new__(cls, value, unit=''):
        if isinstance(value, str):
            value, unit = parse_value(value, accept_invalid=False)
        return float.__new__(cls, value)

    def clean(self) -> 'float_unit':
        """Removes the original string representation, so that the value is formatted with engineering multipliers."""
        self._original = None
        return self

    def __str__(self):
        """Formats values with engineering multipliers preserving unit information."""
        if self._original:
            return self._original
        if math.isnan(self):
            return 'nan'
        return format_eng(self) + self.unit

    __repr__ = __str__

    def is_invalid(self):
        return math.isnan(self)

    def isvalid(self):
        return not math.isnan(self)

    @property
    def unit(self):
        return self._unit.sign

    @property
    def unit_long(self):
        if abs(self) > 1:
            return self._unit.many_name
        else:
            return self._unit.one_name

    @unit.setter
    def unit(self, val):
        self._original = None
        if val in _UNITS:
            self._unit = _UNITS[val]
        else:
            for unit in _UNITS.values():
                if unit.one_name == val or unit.many_name == val:
                    self._unit = unit
                    break
            else:
                raise KeyError("Unit not supported")


    def __add__(self, other):
        return float_unit(float.__add__(float(self), float(other)))

    def __sub__(self, other):
        return float_unit(float.__sub__(float(self), float(other)))

    def __mul__(self, other):
        return float_unit(float.__mul__(float(self), float(other)))

    def __truediv__(self, other):
        return float_unit(float.__truediv__(float(self), float(other)))

    def __eq__(self, other):
        if isinstance(other, str):
            try:
                other = float_unit(other)
            except (ValueError, UnitError):
                return False
        return float.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)


def to_float(value: str | float | int, accept_invalid: bool = True) -> float_unit | str:
    """
    Parse a token into ``float_unit`` whenever possible.

    For backward compatibility, invalid string tokens are returned unchanged
    when ``accept_invalid`` is True.
    """
    if isinstance(value, float_unit):
        return value
    if isinstance(value, (int, float)):
        return float_unit(value)
    if isinstance(value, str):
        try:
            return float_unit(value)
        except (ValueError, UnitError) as err:
            if not accept_invalid:
                raise err

    return value


if __name__ == "__main__":
    def test_float_unit(test, result, **kwargs):
        if result:
            a = float_unit(test, **kwargs)
            if abs(a - result) < 1E-22:
                ok = "PASS"
            else:
                ok = "FAILED"
        else:
            try:
                a = float_unit(test, **kwargs)
            except ValueError:
                a = None
                ok = 'PASSED'
            else:
                ok = 'FAILED'
        print(f"{test} yields {a} : {ok}")
    test_float_unit("R", None)
    test_float_unit("4.63652E+3 Hz", 4.63652E+3)
    test_float_unit("2.2kV", 2200)
    test_float_unit("2.2KV", 2200)
    test_float_unit("2k2", 2200)
    test_float_unit("2E-10", 200E-12)
    print(f"{float_unit(9.63600e+00, 'A')}")
    test_float_unit("3M", 3E+6)
    test_float_unit("33Meg", 33E+6)
    try:
        test_float_unit("33UNDEF", math.nan)
    except:
        print("Invalid test successful")
    else:
        print("Invalid test not successful")
    a = float_unit("33UNDEF")
    print(f'{a} - Is invalid {a.is_invalid()}')
    x = float_unit(1)
    print("Type is :", type(x))
    print("isinstance float", isinstance(x, float))
    x.unit = 'Ohm'
    x.formatting_precision = 0.1
    print(x)
    print(x.formatting_precision)
    x.formatting_precision = 0.001
    print(x)
    print(x.formatting_precision)

    print(f"{x}")
    print(f"{x:f}")
    print(f"{x:e}")
    y = float_unit("1A")
    z = float_unit("1V")
    print(y)
    print(z)
    try:
        c = complex(1, 5)
        test_float_unit(str(c), c)
    except:
        print("Invalid test successful")
    else:
        print("Invalid test not successful")
