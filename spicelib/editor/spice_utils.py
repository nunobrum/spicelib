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
# Name:        spice_utils.py
# Purpose:     Collection of utility functions and constants for SPICE netlist parsing
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import re
from typing import Dict


UNIQUE_SIMULATION_DOT_INSTRUCTIONS = ('.AC', '.DC', '.TRAN', '.NOISE', '.DC', '.TF')
SPICE_DOT_INSTRUCTIONS = (
    '.BACKANNO',
    '.END',
    '.ENDS',
    '.FERRET',  # Downloads a File from a given URL
    '.FOUR',  # Compute a Fourier Component after a .TRAN Analysis
    '.FUNC', '.FUNCTION',
    '.GLOBAL',
    '.IC',
    '.INC', '.INCLUDE',  # Include another file
    '.LIB',  # Include a Library
    '.LOADBIAS',  # Load a Previously Solved DC Solution
    # These Commands are part of the contraption Programming Language of the Arbitrary State Machine
    '.MACHINE', '.STATE', '.RULE', '.OUTPUT', '.ENDMACHINE',
    '.MEAS', '.MEASURE',
    '.MODEL',
    '.NET',  # Compute Network Parameters in a .AC Analysis
    '.NODESET',  # Hints for Initial DC Solution
    '.OP',
    '.OPTIONS',
    '.PARAM', '.PARAMS',
    '.SAVE', '.SAV',
    '.SAVEBIAS',
    '.STEP',
    '.SUBCKT',
    '.CONTROL',  # Start of Control Section
    ".ENDC",  # End of Control Section
    '.TEXT',
    '.WAVE',  # Write Selected Nodes to a .Wav File

)
SUBCKT_CLAUSE_FIND = r"^.SUBCKT\s+"
subckt_regex = re.compile(r"^.SUBCKT\s+(?P<name>[\w\.]+)", re.IGNORECASE)
lib_inc_regex = re.compile(r"^\.(LIB|INC)\s+(.*)$", re.IGNORECASE)



def _first_token_upped(line):
    """
    (Private function. Not to be used directly)
    Returns the first non-space character in the line. If a point '.' is found, then it gets the primitive associated.
    """
    i = 0
    while i < len(line) and line[i] in (' ', '\t'):
        i += 1
    j = i
    while i < len(line) and not (line[i] in (' ', '\t')):
        i += 1
    return line[j:i].upper()



def PREFIX_AND_NODES_RGX(prefix: str, nodes_min: int, nodes_max: int = None, in_quotes: bool = False,
                         qspice_prefix_quirk: bool = False) -> str:
    """Create regex for the designator and nodes. Will not consume a trailing space.

    :param prefix: the prefix character of the element. 1 character.
    :type prefix: str
    :param nodes_min: number of nodes, or minimum number of nodes
    :type nodes_min: int
    :param nodes_max: maximum number of nodes. None means: fixed number of nodes = nodes_min. Defaults to None
    :type nodes_max: int, optional
    :param in_quotes: whether the nodes may be enclosed in quotes « » (qspice). Defaults to False
    :type in_quotes: bool, optional
    :param qspice_prefix_quirk: whether to allow an optional '†' after the prefix, for qspice. Defaults to False
    :return: regex for the designator and nodes
    :rtype: str
    """
    nodes_str = str(nodes_min)
    if nodes_max is not None:
        nodes_str += "," + str(nodes_max)
        # designator: word
        # nodes: 1 or more words with signs and . allowed. DO NOT include '=' (like with \S) as it will mess up params
        # The ¥ is for qspice
    prefix += "[§†]?" if qspice_prefix_quirk else "§?"
    if in_quotes:
        return "^(?P<designator>" + prefix + "\\w+)(?P<nodes>\\s+«(?:\\s?[\\w+-\\.¥«´»]+){" + nodes_str + "}\\s*»)"
    else:
        return "^(?P<designator>" + prefix + "\\w+)(?P<nodes>(?:\\s+[\\w+-\\.¥«»]+){" + nodes_str + "})"

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
    'Ã': PREFIX_AND_NODES_RGX("Ã", 16, qspice_prefix_quirk=True) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # MultGmAmp and RRopAmp
    '¥': PREFIX_AND_NODES_RGX("¥", 16) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Various
    '€': PREFIX_AND_NODES_RGX("€", 32) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # DAC
    '£': PREFIX_AND_NODES_RGX("£", 64) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # Dual Gate Driver
    'Ø': PREFIX_AND_NODES_RGX("Ø´?", 1, 99, in_quotes=True) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # DLL
    '×': PREFIX_AND_NODES_RGX("×", 4, 100, in_quotes=True) + NO_VALUE_RGX + PARAM_RGX,  # transformer

    # LTSPICE Unique components:
    'Ö': PREFIX_AND_NODES_RGX("Ö", 5) + MODEL_OR_VALUE_RGX + PARAM_RGX,  # specialised OTA
}
VALID_PREFIXES = REPLACE_REGEXS.keys()
