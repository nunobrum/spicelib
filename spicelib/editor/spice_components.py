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
# Name:        spice_components.py
# Purpose:     Parse and manipulate SPICE components in a netlist
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from collections import OrderedDict
from typing import Dict
import re
import io
import logging

from .editor_errors import UnrecognizedSyntaxError
from .primitives import Component, format_eng, VALUE_IDs, PARAMS_IDs
from .updates import UpdateType
from ..log.logfile_data import try_convert_value

_logger = logging.getLogger("spicelib.SpiceEditor")


def PREFIX_AND_NODES_RGX(prefix: str, nodes_min: int, nodes_max: int = None, in_quotes: bool = False) -> str:
    """Create regex for the designator and nodes. Will not consume a trailing space.

    :param prefix: the prefix character of the element. 1 character.
    :type prefix: str
    :param nodes_min: number of nodes, or minimum number of nodes
    :type nodes_min: int
    :param nodes_max: maximum number of nodes. None means: fixed number of nodes = nodes_min. Defaults to None
    :type nodes_max: int, optional
    :param in_quotes: whether the nodes may be enclosed in quotes « » (qspice). Defaults to False
    :type in_quotes: bool, optional
    :return: regex for the designator and nodes
    :rtype: str
    """
    nodes_str = str(nodes_min)
    if nodes_max is not None:
        nodes_str += "," + str(nodes_max)
        # designator: word
        # nodes: 1 or more words with signs and . allowed. DO NOT include '=' (like with \S) as it will mess up params
        # The ¥ is for qspice
    if in_quotes:
        return "^(?P<designator>" + prefix + "§?\\w+)(?P<nodes>\\s+«(?:\\s?[\\w+-\\.¥«´»]+){" + nodes_str + "}\\s*»)"
    else:
        return "^(?P<designator>" + prefix + "§?\\w+)(?P<nodes>(?:\\s+[\\w+-\\.¥«»]+){" + nodes_str + "})"


END_LINE_TERM = '\n'  #: This controls the end of line terminator used

# Regular expressions for the different components
# FLOAT_RGX = r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"

# Regular expression for a number with decimal qualifier and unit
# NUMBER_RGX = FLOAT_RGX + r"(Meg|[kmuµnpfgt])?[a-zA-Z]*"

# Optional comment at end of line. Will consume trailing spaces and is to be used on all lines.
COMMENT_RGX = r"(?:\s+;.*)?\\?\s*$"

# Potential model name, probably needs expanding. Will require a leading space
MODEL_OR_VALUE_RGX = r"\s+(?P<value>[\w\.\-\{\}]+)"

# the rest of the line. Cannot be used with PARAM.
# Includes the comment regex and will expect to finish the line.
ANY_VALUE_RGX = r"\s+(?P<value>.*)" + COMMENT_RGX

# maybe a value. Will require a leading space
MAYBE_VALUE_RGX = r"\s+(?P<value>.*?)"

# no value
NO_VALUE_RGX = r"\s?(?P<value>)?"

# Parameters expression of the type: key = value.
# key must be a full word without signs or dots
# Value may be composite, and contain multiple spaces and quotes.
# Includes the comment regex and will expect to finish the line.
PARAM_RGX = r"(?P<params>(\s+\w+\s*(=\s*[\w\{\}\(\)\-\+\*\/%\.\,'\"\s]+)?)*)?" + COMMENT_RGX

def VALUE_RGX(prefix: str, number_regex_suffix: str) -> str:
    """Regex for a value, or a formula that is a single word, or is enclosed by "" or '' or {}.
    Will require a leading space, but not a trailing space.

    :param prefix: optional parameter style prefix letter for the value matching. Must be empty or 1 character.
    :type prefix: str
    :param number_regex_suffix: a regex that represents any decimal qualifiers or units
    :type number_regex_suffix: str
    :return: the regex for a regular value
    :rtype: str
    """
    my_prefix = ""
    if len(prefix) == 1:
        my_prefix = "(" + prefix + "\\s?=\\s?)?"
    return "\\s+" + my_prefix + "(?P<value>(?P<number>[-+]?[0-9]*\\.?[0-9]+([eE][-+]?[0-9]+)?" + \
        number_regex_suffix + ")?(?P<formula1>\")?(?P<formula2>')?(?P<formula3>{)?" + \
        "(?(number)|(?(formula1).*\"|(?(formula2).*'|(?(formula3).*}|\\S*)))))"


REPLACE_REGEXS : Dict[str, str] = {
    'A': r"",  # LTspice Only : Special Functions, Parameter substitution not supported
    # Bxxx n001 n002 [VIRP]=<expression> [ic=<value>] ...
    'B': PREFIX_AND_NODES_RGX("B", 2) + r"\s+(?P<value>[VIBR]\s*=(\s*[\w\{\}\(\)\-\+\*\/%\.\<\>\?\:\"\']+)*)" + PARAM_RGX,  # Behavioral source
    # Cxxx n1 n2 <capacitance> [ic=<value>] ...
    # Cxxx n+ n- <value> <mname> <m=val> <scale=val> <temp=val> ...
    # Cxxx n1 n2 C=<capacitance> [ic=<value>] ...
    # Cxxx n1 n2 Q=<expression> [ic=<value>] [m=<value>] ...
    'C': PREFIX_AND_NODES_RGX("C", 2) + VALUE_RGX("C", r"[muµnpfgt]?F?\d*") + PARAM_RGX,  # Capacitor
    # Dxxx anode cathode <model> [area] [off] [m=<val>] [n=<val>] [temp=<value>] ...
    # Dxxx n+ n- mname <area=val> <m=val> <pj=val> <off> ...
    'D': PREFIX_AND_NODES_RGX("D", 2) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Diode
    # Exxx n+ n- nc+ nc- <gain>
    # Exxx n+ n- nc+ nc- table=(<value pair>, <value pair>, ...)
    # Exxx n+ n- nc+ nc- Laplace=<func(s)>...
    # Exxx n+ n- value={<expression>}
    # Exxx n+ n- POLY(<N>) <(node1+,node1-) (node2+,node2-)+ ... (nodeN+,nodeN-)> <c0 c1 c2 c3 c4 ...>
    'E': PREFIX_AND_NODES_RGX("E", 2) + ANY_VALUE_RGX,  # Voltage Dependent Voltage Source
    # Fxxx n+ n- <Vnam> <gain>
    # Fxxx n+ n- value={<expression>}
    # Fxxx n+ n- POLY(<N>) <V1 V2 ... VN> <c0 c1 c2 c3 c4 ...>
    'F': PREFIX_AND_NODES_RGX("F", 2) + ANY_VALUE_RGX,  # Current Dependent Current Source
    # Gxxx n+ n- nc+ nc- <gain>
    # Gxxx n+ n- nc+ nc- table=(<value pair>, <value pair>, ...)
    # Gxxx n+ n- nc+ nc- Laplace=<func(s)> [window=<time>] [nfft=<number>] [mtol=<number>]
    # Gxxx n+ n- nc+ nc- value={<expression>}
    # Gxxx n+ n- POLY(<N>) <(node1+,node1-) (node2+,node2-) ... (nodeN+,nodeN-)> <c0 c1 c2 c3 c4 ...>
    'G': PREFIX_AND_NODES_RGX("G", 2) + ANY_VALUE_RGX,  # Voltage Dependent Current Source
    # Hxxx n+ n- <Vnam> <transresistance>
    # Hxxx n+ n- value={<expression>}
    # Hxxx n+ n- POLY(<N>) <V1 V2 ... VN> <c0 c1 c2 c3 c4 ...>
    'H': PREFIX_AND_NODES_RGX("H", 2) + ANY_VALUE_RGX,  # Voltage Dependent Current Source
    # Ixxx n+ n- <current> [AC=<amplitude>] [load]
    # Ixxx n+ n- PULSE(Ioff Ion Tdelay Trise Tfall Ton Tperiod Ncycles)
    # Ixxx n+ n- SINE(Ioffset Iamp Freq Td Theta Phi Ncycles)
    # Ixxx n+ n- EXP(I1 I2 Td1 Tau1 Td2 Tau2)
    # Ixxx n+ n- SFFM(Ioff Iamp Fcar MDI Fsig)
    # Ixxx n+ n- <value> step(<value1>, [<value2>], [<value3>, ...]) [load]
    # Ixxx n+ n- R=<value>
    # Ixxx n+ n- PWL(t1 i1 t2 i2 t3 i3...)
    # Ixxx n+ n- wavefile=<filename> [chan=<nnn>]
    'I': PREFIX_AND_NODES_RGX("I", 2) + MAYBE_VALUE_RGX + r"(?P<params>(\s+\w+\s*=\s*[\w\{\}\(\)\-\+\*\/%\.\,'\"\s]+)*)" + COMMENT_RGX,  # Independent Current Source
    # Jxxx D G S <model> [area] [off] [IC=Vds, Vgs] [temp=T]
    'J': PREFIX_AND_NODES_RGX("J", 3) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # JFET
    # Kxxx Lyyy Lzzz ... value
    'K': PREFIX_AND_NODES_RGX("K", 2, 99) + r"\s+(?P<value>[\+\-]?[0-9\.E+-]+[kmuµnpgt]?)" + COMMENT_RGX,  # Mutual Inductance
    # Lxxx n+ n- <value> <mname> <nt=val> <m=val> ...
    # Lxxx n+ n- L = 'expression' <tc1=value> <tc2=value>
    'L': PREFIX_AND_NODES_RGX("L", 2) + VALUE_RGX("L", r"(Meg|[kmuµnpgt])?H?\d*") + PARAM_RGX,  # Inductance
    # Mxxx Nd Ng Ns Nb <model> [m=<value>] [L=<len>] ...
    # Mxxx Nd Ng Ns <model> [L=<len>] [W=<width>]
    'M': PREFIX_AND_NODES_RGX("M", 3, 4) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # MOSFET
    # Nxxx NI1 NI2...NIX mname [<parameter>=<value>] ...
    'N': PREFIX_AND_NODES_RGX("N", 2, 99) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Verilog-A Compact Device (ngspice/openvaf)
    # Oxxx L+ L- R+ R- <model>
    'O': PREFIX_AND_NODES_RGX("O", 4) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Lossy Transmission Line
    # Pxxx NI1 NI2...NIX GND1 NO1 NO2...NOX GND2 mname <LEN=LENGTH>
    'P': PREFIX_AND_NODES_RGX("P", 2, 99) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Coupled Multiconductor Line (ngspice) or Port Device (xyce)
    # Qxxx nc nb ne <ns> <tj> mname <area=val> <areac=val> ...
    # Qxxx Collector Base Emitter [Substrate Node] model [area] [off] [IC=<Vbe, Vce>] [temp=<T>]
    'Q': PREFIX_AND_NODES_RGX("Q", 3, 5) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Bipolar
    # Rxxx n1 n2 <value> [tc=tc1, tc2, ...] [temp=<value>] ...
    # Rxxx n+ n- <value> <mname> <l=length> <w=width> ...
    # Rxxx n+ n- R = 'expression' <tc1=value> <tc2=value> <noisy=0> ...
    'R': PREFIX_AND_NODES_RGX("R", 2) + VALUE_RGX("R", r"(Meg|[kmuµnpfgt])?R?\d*") + PARAM_RGX,  # Resistor
    # Sxxx n1 n2 nc+ nc- <model> [on,off]
    'S': PREFIX_AND_NODES_RGX("S", 4) + ANY_VALUE_RGX,  # Voltage Controlled Switch
    # Txxx L+ L- R+ R- Zo=<value> Td=<value>
    'T': PREFIX_AND_NODES_RGX("T", 4) + NO_VALUE_RGX + PARAM_RGX,  # Lossless Transmission
    # (ltspice and ngspice) Uxxx N1 N2 Ncom <model> L=<len> [N=<lumps>]
    # (xyce) U<name> <type> <digital power node> <digital ground node> [node]* <model name>
    'U': PREFIX_AND_NODES_RGX("U", 3) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Uniform RC-line (ltspice and ngspice)
    # Vxxx n+ n- <voltage> [AC=<amplitude>] [Rser=<value>] [Cpar=<value>]
    # Vxxx n+ n- PULSE(V1 V2 Tdelay Trise Tfall Ton Tperiod Ncycles)
    # Vxxx n+ n- SINE(Voffset Vamp Freq Td Theta Phi Ncycles)
    # Vxxx n+ n- EXP(V1 V2 Td1 Tau1 Td2 Tau2)
    # Vxxx n+ n- SFFM(Voff Vamp Fcar MDI Fsig)
    # Vxxx n+ n- PWL(t1 v1 t2 v2 t3 v3...)
    # Vxxx n+ n- wavefile=<filename> [chan=<nnn>]
    # ex: V1 NC_08 NC_09 PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) AC 1 2 Rser=3 Cpar=4
    'V': PREFIX_AND_NODES_RGX("V", 2) + MAYBE_VALUE_RGX + r"(?P<params>(\s+\w+\s*=\s*[\w\{\}\(\)\-\+\*\/%\.\,'\"\s]+)*)" + COMMENT_RGX,  # Independent Voltage Source
    # Wxxx n1 n2 Vnam <model> [on,off]
    'W': PREFIX_AND_NODES_RGX("W", 3) + ANY_VALUE_RGX,  # Current Controlled Switch
    # Xxxx n1 n2 n3... <subckt name> [<parameter>=<expression>]
    # ex: XU1 NC_01 NC_02 NC_03 NC_04 NC_05 level2 Avol=1Meg GBW=10Meg Slew=10Meg Ilimit=25m Rail=0 Vos=0 En=0 Enk=0 In=0 Ink=0 Rin=500Meg
    #     XU1 in out1 -V +V out1 OPAx189 bla_v2 =1% bla_sp1=2 bla_sp2 = 3
    #     XU1 in out1 -V +V out1 GND OPAx189_float
    'X': PREFIX_AND_NODES_RGX("X", 1, 99) + MODEL_OR_VALUE_RGX + r"(?:\s+(?P<params>(?:\w+\s*=\s*['\"{]?.*?['\"}]?\s*)+))?" + COMMENT_RGX,  # Subcircuit Instance
    # (ngspice) Yxxx N1 0 N2 0 mname <LEN=LENGTH>
    # (qspice) Ynnn N+ N- <frequency1> dF=<value> Ctot=<value> [Q=<value>]
    'Y': PREFIX_AND_NODES_RGX("Y", 2, 4) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Single Lossy Transmission Line
    # Zxxx D G S model [area] [m=<value>] [off] [IC=<Vds, Vgs>] [temp=<value>]
    'Z': PREFIX_AND_NODES_RGX("Z", 3) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # MESFET, IBGT

    # TODO
    '@': r"^(?P<designator>@§?\d+)(?P<nodes>(\s+\S+){2})\s?(?P<params>(.*)*)$",

    # TODO: Frequency Noise Analysis (FRA) wiggler
    # pattern = r'^@(\d+)\s+(\w+)\s+(\w+)(?:\s+delay=(\d+\w+))?(?:\s+fstart=(\d+\w+))?(?:\s+fend=(\d+\w+))?(?:\s+oct=(\d+))?(?:\s+fcoarse=(\d+\w+))?(?:\s+nmax=(\d+\w+))?\s+(\d+)\s+(\d+\w+)\s+(\d+)(?:\s+pp0=(\d+\.\d+))?(?:\s+pp1=(\d+\.\d+))?(?:\s+f0=(\d+\w+))?(?:\s+f1=(\d+\w+))?(?:\s+tavgmin=(\d+\w+))?(?:\s+tsettle=(\d+\w+))?(?:\s+acmag=(\d+))?$'

    # QSPICE Unique components:
    # Ãnnn VDD VSS OUT IN- IN+ MULT+ MULT- IN-- IN++ EN ¥ ¥ ¥ ¥ ¥ ¥ <TYPE> [INSTANCE PARAMETERS]
    # etc...
    'Ã': PREFIX_AND_NODES_RGX("Ã", 16) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # MultGmAmp and RRopAmp
    '¥': PREFIX_AND_NODES_RGX("¥", 16) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Various
    '€': PREFIX_AND_NODES_RGX("€", 32) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # DAC
    '£': PREFIX_AND_NODES_RGX("£", 64) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Dual Gate Driver
    'Ø': PREFIX_AND_NODES_RGX("Ø´?", 1, 99, in_quotes=True) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # DLL
    '×': PREFIX_AND_NODES_RGX("×", 4, 100, in_quotes=True) + NO_VALUE_RGX + PARAM_RGX,  # transformer

    # LTSPICE Unique components:
    'Ö': PREFIX_AND_NODES_RGX("Ö", 5) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # specialised OTA
}
VALID_PREFIXES = REPLACE_REGEXS.keys()

# Code Optimization objects, avoiding repeated compilation of regular expressions
component_replace_regexs: Dict[str, re.Pattern] = {}
for prefix, pattern in REPLACE_REGEXS.items():
    # print(f"Compiling regex for {prefix}: {pattern}")
    component_replace_regexs[prefix] = re.compile(pattern, re.IGNORECASE)


def _clean_line(line: str) -> str:
    """remove extra spaces and clean up the line so that the regexes have an easier time matching

    :param line: spice netlist string
    :type line: str
    :return: spice netlist string cleaned up
    :rtype: str
    """
    if line is None:
        return ""
    # Remove any leading or trailing spaces
    line = line.strip()
    # condense all space sequences to a single space
    line = re.sub(r'\s+', ' ', line).strip()
    # Remove any spaces before or after the '=' sign
    line = line.replace(" =", "=")
    line = line.replace("= ", "=")
    # Remove any spaces before or after the ',' sign (for constructions like "key=val1, val2")
    line = line.replace(" ,", ",")
    line = line.replace(", ", ",")
    return line


def _parse_params(params_str: str) -> dict:
    """
    Parses the parameters string and returns a dictionary with the parameters.
    The parameters are in the form of key=value, separated by spaces.
    The values may contain spaces or sequences with comma separation

    :param params_str: input
    :type params_str: str
    :raises ValueError: invalid format
    :return: dict with parameters
    :rtype: dict
    """
    params = OrderedDict()
    # make sure all spaces are condensed and there are no spaces around the = sign
    params_str = _clean_line(params_str)
    if len(params_str) == 0:
        return params

    # now split in pairs
    # This will match key=value pairs, where value may contain spaces, but not unescaped '=' signs

    # TODO in case of a qspice verilog component (Ø), allow "type key=value", but that is not easy to do, as we do not know the component type here
    # Here are the allowed types, just in case this will be correctly implemented one day:
    # verilog_types = [
    #     "bit",
    #     "bool",
    #     "boolean",
    #     "int8_t",
    #     "int8",
    #     "char",
    #     "char",
    #     "uint8_t",
    #     "uint8",
    #     "uchar",
    #     "uchar",
    #     "byte",
    #     "int16_t",
    #     "int16",
    #     "uint16_t",
    #     "uint16",
    #     "int32_t",
    #     "int32",
    #     "int",
    #     "uint32_t",
    #     "uint32",
    #     "uint",
    #     "int64_t",
    #     "int64",
    #     "uint64_t",
    #     "uint64",
    #     "shortfloat",
    #     "float",
    #     "double",
    # ]
    pattern = r"(\w+)=(.*?)(?<!\\)(?=\s+\w+=|$)"
    matches = re.findall(pattern, params_str)
    if matches:
        for key, value in matches:
            params[key] = try_convert_value(value)
        return params
    else:
        raise ValueError(f"Invalid parameter format: '{params_str}'")

def _insert_section(line: str, start: int, end: int, section: str) -> str:
    """
    Inserts a section in the line at the given start and end positions.
    Makes sure the section is surrounded by spaces and the line ends with a newline
    """
    if not line:
        return ""
    if not section:  # Nothing to insert
        return line

    section = section.strip()
    # TODO why do we need a space? In the construction 'a=1' that must become 'a=2' a space should not be needed.
    if start > 0 and line[start - 1] != ' ':
        section = ' ' + section
    if end < len(line) and line[end] != ' ' and len(section) > 1:
        section = section + ' '
    line = line[:start] + section + line[end:]
    line = line.strip()
    return line

class SpiceComponent(Component):
    """
    Represents a SPICE component in the netlist. It allows the manipulation of the parameters and the value of the
    component.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the SpiceComponent"""
        super().__init__(*args, **kwargs)

    # def absolute_reference(self) -> str:
    #     """Get the absolute reference of the component inside the netlist
    #
    #     :return: absolute reference
    #     :rtype: str
    #     """
    #     if self._netlist is not None:
    #         return self._netlist.parent_reference() + self.reference
    #     return self.reference

    def reset_attributes(self):
        """Update attributes of a component at a specific line in the netlist

        :raises NotImplementedError: When the component type is not recognized
        :raises UnrecognizedSyntaxError: When the line doesn't match the expected REGEX.
        :return: The match found
        :rtype: re.match

        :meta private:
        """
        prefix = self._obj[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {self._obj}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        new_line = re.sub(r'[\n\r]+\s*', ' ', self._obj) # cleans up line breaks and extra spaces and tabs
        match = regex.match(new_line)
        if match is None:
            raise UnrecognizedSyntaxError(self._obj, regex.pattern)

        info = match.groupdict()
        self.attributes.clear()
        for attr in info:
            if attr == 'designator':
                ref = info[attr]
                if len(ref) > 2 and ref[1] == '§':
                    # strip any §, it is not always present and seems optional, so scrap it
                    ref = ref[0] + ref[2:]
                self.reference = ref
            elif attr == 'nodes':
                self.ports = info[attr].split()
            elif attr == 'params':
                if info[attr]:
                    self.set_params(**_parse_params(info[attr]))
            elif attr in ('number', 'formula1', 'formula2', 'formula3'):
                continue  # these are subgroups of VALUE, ignore
            else:
                if info[attr] is not None:  # Only sets attributes that are present
                    setattr(self, attr, info[attr])
        return match

    def rewrite_lines(self, stream: io.StringIO) -> int:
        """Write the SPICE representation of the component into a stream

        :return: Number of characters written
        :rtype: int
        """
        # Reconstruct the line from the attributes. This will not preserve the original formatting, by reparsing
        # again the line updating the parameters.
        prefix = self.reference[0]
        regex = component_replace_regexs.get(prefix, None)
        if regex is None:
            error_msg = f"Component must start with one of these letters: {','.join(REPLACE_REGEXS.keys())}\n" \
                        f"Got {self._obj}"
            _logger.error(error_msg)
            raise NotImplementedError(error_msg)
        match = regex.match(self._obj)
        if match is None:
            raise UnrecognizedSyntaxError(self._obj, regex.pattern)
        info = match.groupdict()
        new_line = self._obj[:]  # make a copy
        new_line = re.sub(r'[\n\r]+\s*', ' ', new_line)
        offset = 0
        update_done = False
        for attr in info:
            start, stop = match.span(attr)
            if attr == 'designator':
                old_ref = info[attr]
                if len(old_ref) > 2 and old_ref[1] == '§':
                    # strip any §, it is not always present and seems optional, so scrap it
                    old_ref = old_ref[0] + old_ref[2:]
                    add_odd_char = True
                else:
                    add_odd_char = False
                if self.reference != old_ref:
                    if add_odd_char:
                        new_ref = self.reference[0] + '§' + self.reference[1:]
                    else:
                        new_ref = self.reference
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_ref)
                    offset += len(new_ref) - len(old_ref)
                    update_done = True
            elif attr == 'nodes':
                old_nodes_str = info[attr]
                new_nodes_str = ' '+ ' '.join(self.ports)
                if old_nodes_str != new_nodes_str:
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_nodes_str)
                    offset += len(new_nodes_str) - len(old_nodes_str)
                    update_done = True
            elif attr == 'params':
                old_params_str = info[attr] or ""  # in case of no params, make it empty string
                new_params_dict = self.params
                new_params_str = ' '.join(f"{key}={value}" for key, value in new_params_dict.items())
                if old_params_str != new_params_str:
                    new_line = _insert_section(new_line, start + offset, stop + offset, new_params_str)
                    offset += len(new_params_str) - len(old_params_str)
                    update_done = True
            else:
                old_attr_value = info[attr]
                if hasattr(self, attr):
                    if isinstance(self[attr], (int, float)):
                        new_attr_value = format_eng(self[attr])
                    else:
                        new_attr_value = str(self[attr])
                    if old_attr_value != new_attr_value:
                        new_line = _insert_section(new_line, start + offset, stop + offset, new_attr_value)
                        offset += len(new_attr_value) - len(old_attr_value)
                        update_done = True
                else:
                    pass  # attribute not present, do nothing
        if not update_done:
            # nothing changed, write original line
            new_line = self._obj
        else:
            new_line += END_LINE_TERM
        stream.write(new_line)
        return len(new_line)

    def write_lines(self, stream: io.StringIO) -> int:
        """Get the SPICE representation of the component as a string. This creates a new line from the attributes alone

        :return: number of characters written
        :rtype: int
        """
        if self._obj != "":
            # try to rewrite the line preserving formatting
            return self.rewrite_lines(stream)

        # Write a line from the stored attributes
        count = stream.write(self.reference)
        for port in self.ports:
            count += stream.write(f" {port}")
        # Write value if present
        if 'value' in self.attributes:
            count += stream.write(f" {self.value_str}")
        if 'model' in self.attributes:
            count += stream.write(f" {self.model}")
        # Write parameters
        line_size = count
        for key, value in self.params.items():
            if line_size == 0:
                count += stream.write("+") # continuation line
                line_size = 1
            chars = stream.write(f" {key}={value}")
            count += chars
            line_size += chars
            if line_size > 80:
                stream.write("\n")  # continuation line
                line_size = 0  # account for the space at the beginning of the new line

        stream.write(END_LINE_TERM)
        count += len(END_LINE_TERM)
        return count

    # def set_value(self, value):
    #     """Informs the netlist that the value of the component has changed"""
    #     super().set_value(value)
    #     self.netlist.add_update(self.reference, value, UpdateType.UpdateComponentValue)
    #
    # def set_params(self, **params):
    #     """Informs the netlist that the parameters of the component have changed"""
    #     super().set_params(**params)
    #     self.netlist.add_update(self.reference,  str(params), UpdateType.UpdateComponentParameter)
    #
    # def set_param(self, key: str, value):
    #     """Informs the netlist that a parameter of the component has changed"""
    #     super().set_param(key, value)
    #     self.netlist.add_update(self.reference, f"{key}={value}", UpdateType.UpdateComponentParameter)




