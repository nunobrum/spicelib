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
# Name:        test_spice_editor.py
# Purpose:     Tool used validate the Spice Files Editor
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import os
import sys
import unittest

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path

import spicelib
from spicelib.editor.base_editor import to_float
from spicelib.editor.spice_editor import component_replace_regexs, SpiceCircuit
from spicelib.editor.updates import UpdateType

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)


def check_value(test, regex, line, value, msg=None):
    r = regex.match(line)
    test.assertIsNotNone(r, "Accepted regex")
    value_str = r.group('value')
    if isinstance(value, str):
        value_test = value_str
    else:
        try:
            value_test = to_float(value_str)
        except ValueError:
            value_test = value_str
    if msg is None:
        msg = f"Pass {value} for {line}"

    if isinstance(value_test, float):
        test.assertAlmostEqual(value_test, value, 6, msg)
    else:
        test.assertEqual(value_test, value, msg)


class SpiceEditor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.SpiceEditor(test_dir + "DC sweep.net")
        self.edt2 = spicelib.SpiceEditor(test_dir + "opamptest.net")
        self.edt3 = spicelib.SpiceEditor(test_dir + "/amp3/amp3.net")

    def check_update(self, editor: SpiceCircuit, name, update, value=None, index=-1):
        self.assertEqual(name, editor.netlist_updates[index].name, "Name mismatch")
        self.assertEqual(update, editor.netlist_updates[index].updates, "Update Type mismatch")
        if update not in (UpdateType.DeleteParameter, UpdateType.DeleteComponent, UpdateType.DeleteComponentParameter):
            self.assertEqual(value, editor.netlist_updates[index].value, "Value mismatch")

    def test_component_editing_1(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10k', "Tested R1 Value")  # add assertion here
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")  # add assertion here
        self.assertEqual(0, len(self.edt.netlist_updates), "There is no update")
        self.edt.set_component_value('R1', '33k')
        self.check_update(self.edt, 'R1', UpdateType.UpdateComponentValue, '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.net')
        self.equalFiles(temp_dir + 'test_components_output.net', golden_dir + 'test_components_output.net')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.edt.set_component_parameters('R1', Tc1=0, Tc2=0, pwr=None)
        self.assertEqual(4, len(self.edt.netlist_updates))
        self.check_update(self.edt, 'R1:Tc1', UpdateType.AddComponentParameter, 0, 1)
        self.check_update(self.edt, 'R1:Tc2', UpdateType.AddComponentParameter, 0, 2)
        self.check_update(self.edt, 'R1:pwr', UpdateType.DeleteComponentParameter, 0, 3)
        self.edt.save_netlist(temp_dir + 'test_components_output_2.net')
        self.equalFiles(temp_dir + 'test_components_output_2.net', golden_dir + 'test_components_output_2.net')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.assertEqual(5, len(self.edt.netlist_updates), "Updated existing update")
        self.check_update(self.edt, 'R1', UpdateType.DeleteComponent)
        self.edt.save_netlist(temp_dir + 'test_components_output_1.net')
        self.equalFiles(temp_dir + 'test_components_output_1.net', golden_dir + 'test_components_output_1.net')

    def test_component_editing_1_obj(self):
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")
        r1 = self.edt['R1']
        self.assertEqual(r1.value_str, '10k', "Tested R1 Value")
        self.assertEqual(r1.value, 10000, "Tested R1 Numeric Value")
        self.assertListEqual(r1.ports, ['in', 'out'], "Tested R1 Nodes")
        r1.value = '33k'
        self.assertEqual(r1.value_str, '33k', "Tested R1 Value")
        self.check_update(self.edt, 'R1', UpdateType.UpdateComponentValue, '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.net')
        self.equalFiles(temp_dir + 'test_components_output.net', golden_dir + 'test_components_output.net')
        self.assertEqual(self.edt['R1'].value_str, '33k', "Tested R1 Value")
        r1['Tc1'] = 0
        r1['Tc2'] = 0
        r1['pwr'] = None
        self.assertEqual(4, len(self.edt.netlist_updates))
        self.check_update(self.edt, 'R1:Tc1', UpdateType.AddComponentParameter, 0, 1)
        self.check_update(self.edt, 'R1:Tc2', UpdateType.AddComponentParameter, 0, 2)
        self.check_update(self.edt, 'R1:pwr', UpdateType.DeleteComponentParameter, 0, 3)
        self.assertEqual(r1.params['Tc1'], 0, "Tested R1 Tc1 Parameter")
        self.assertEqual(r1.params['Tc2'], 0, "Tested R1 Tc2 Parameter")
        self.edt.save_netlist(temp_dir + 'test_components_output_2.net')
        self.equalFiles(temp_dir + 'test_components_output_2.net', golden_dir + 'test_components_output_2.net')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
            self.assertEqual(r1[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.edt.save_netlist(temp_dir + 'test_components_output_1.net')
        self.equalFiles(temp_dir + 'test_components_output_1.net', golden_dir + 'test_components_output_1.net')

    def test_component_editing_2(self):
        self.assertEqual(self.edt2.get_component_value('V1'), '15', "Tested V1 Value")
        self.assertEqual(self.edt2.get_component_value('V3'), 'PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) AC 1', "Tested V3 Value")  # complex value, with parameters
        self.assertEqual(self.edt2.get_component_value('XU1'), 'level2', "Tested U1 Value")  # has parameters
        self.assertEqual(self.edt2.get_component_parameters('XU1')['Rin'], '501Meg', "Tested U1 Rin Value")  # last in the list
        self.assertEqual(self.edt2.get_component_value('XU2'), 'AD549', "Tested U2 Value")  # no parameters
        self.assertListEqual(self.edt2.get_components(), ['V1', 'V2', 'V3', 'XU1', 'XU2'], "Tested get_components")
        self.edt2.set_component_value('V3', 'PWL(2u 0 +1p 1 +1m 1)')
        self.assertEqual(1, len(self.edt2.netlist_updates))
        self.check_update(self.edt2, 'V3', UpdateType.UpdateComponentValue, 'PWL(2u 0 +1p 1 +1m 1)')
        self.edt2.set_component_parameters('V3', Rser=1)  # first in the list
        self.check_update(self.edt2, 'V3:Rser', UpdateType.UpdateComponentParameter, 1)
        self.edt2.set_component_value('XU1', 'level3')
        self.check_update(self.edt2, 'XU1', UpdateType.UpdateComponentValue, 'level3')
        self.edt2.set_component_parameters('XU1', GBW='1Meg')  # somewhere in the list
        self.check_update(self.edt2, 'XU1:GBW', UpdateType.UpdateComponentParameter, '1Meg')
        self.edt2.save_netlist(temp_dir + 'opamptest_output_1.net')
        self.equalFiles(temp_dir + 'opamptest_output_1.net', golden_dir + 'opamptest_output_1.net')

    def test_parameter_edit(self):
        self.assertEqual(self.edt.get_all_parameter_names(), ['RES', 'TEMP'])
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameter('TEMP', 25)
        self.check_update(self.edt, 'TEMP', UpdateType.UpdateParameter, 25)
        self.assertEqual(self.edt.get_parameter('TEMP'), '25', "Tested TEMP Parameter")  # add assertion here
        self.edt.save_netlist(temp_dir + 'test_parameter_output.net')
        self.equalFiles(temp_dir + 'test_parameter_output.net', golden_dir + 'test_parameter_output.net')
        self.edt.set_parameter('TEMP', 0)  # reset to 0
        self.check_update(self.edt, 'TEMP', UpdateType.UpdateParameter, 0)
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameters(floatpparam=1.23, signed_param=-0.99, expparam=-1E-34)
        self.check_update(self.edt, 'floatpparam', UpdateType.UpdateParameter, 1.23, 1)
        self.check_update(self.edt, 'signed_param', UpdateType.UpdateParameter, -0.99, 2)
        self.check_update(self.edt, 'expparam', UpdateType.UpdateParameter, -1E-34, 3)
        self.edt.save_netlist(temp_dir + 'test_parameter_output_1.net')
        self.equalFiles(temp_dir + 'test_parameter_output_1.net', golden_dir + 'test_parameter_output_1.net')

    def test_instructions(self):
        self.edt.add_instruction('.ac dec 10 1 100k')
        self.edt.add_instruction('.save V(vout)')
        self.edt.add_instruction('.save I(R1)')
        self.edt.add_instruction('.save I(R2)')
        self.edt.add_instruction('.save I(D1)')
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.AddInstruction, '.ac dec 10 1 100k', 0)
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.AddInstruction, '.save V(vout)', 1)
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.AddInstruction, '.save I(R1)', 2)
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.AddInstruction, '.save I(R2)', 3)
        self.edt.save_netlist(temp_dir + 'test_instructions_output.net')
        self.equalFiles(temp_dir + 'test_instructions_output.net', golden_dir + 'test_instructions_output.net')
        self.edt.remove_instruction('.save I(R1)')
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.DeleteInstruction, '.save I(R1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_1.net')
        self.equalFiles(temp_dir + 'test_instructions_output_1.net', golden_dir + 'test_instructions_output_1.net')
        self.edt.remove_Xinstruction(r"\.save\sI\(.*\)")  # removes all .save instructions for currents
        self.check_update(self.edt, 'INSTRUCTION', UpdateType.DeleteInstruction, '.save I(D1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_2.net')
        self.equalFiles(temp_dir + 'test_instructions_output_2.net', golden_dir + 'test_instructions_output_2.net')

    def equalFiles(self, file1, file2):
        with open(file1, 'r') as f1:
            lines1 = f1.readlines()
        with open(file2, 'r') as f2:
            lines2 = f2.readlines()
        self.assertEqual(len(lines1), len(lines2), "Files have different number of lines\n"
                                                   f"File1:{file1} and File2:{file2}")
        for i, lines in enumerate(zip(lines1, lines2)):
            self.assertEqual(lines[0], lines[1], f"Line {i}\nFile1:{file1} and File2:{file2}")

    def test_resistors(self):
        """Validates the RegEx expressions on the Spice Editor file"""

        # Resistors
        regex_r = component_replace_regexs['R']
        self.assertIsNone(regex_r.match('X12 N1 N2 10k'), "Invalid prefix")

        check_value(self, regex_r, "Rq N1 N2 10k", '10k')
        check_value(self, regex_r, "Rq N1 N2 10R3", 10.3)
        check_value(self, regex_r, "Rq N1 N2 10k5", 10500)
        check_value(self, regex_r, "Rq N1 N2 10K6", 10600)
        check_value(self, regex_r, "Rq N1 N2 11Meg", 11E6)
        check_value(self, regex_r, "Rq N1 N2 10Meg5", 10.5e6)
        check_value(self, regex_r, "Rq N1 N2 {param1 + Param2}", "{param1 + Param2}")

    def test_capacitors(self):
        regex_c = component_replace_regexs['C']
        self.assertIsNone(regex_c.match('X12 N1 N2 10k'), "Invalid prefix")

        check_value(self, regex_c, "C10 N1 N2 10u", 10e-6)
        check_value(self, regex_c, "CX N1 N2 1U", 1e-6)
        check_value(self, regex_c, "Cq N1 N2 1UF", 1e-6)
        check_value(self, regex_c, "Cq N1 N2 120p", 12.0E-12)
        check_value(self, regex_c, "Cq N1 N2 12pF", 12.0E-12)
        check_value(self, regex_c, "Cq N1 N2 10.3E-9", 10.3E-9)
        check_value(self, regex_c, "Cq N1 N2 12e-12", 1e-12)
        check_value(self, regex_c, "Cq N1 N2 {param*2+3}", "{param*2+3}")

    def test_inductors(self):
        regex_l = component_replace_regexs['L']
        self.assertIsNone(regex_l.match('X12 N1 N2 10k'), "Invalid prefix")

        check_value(self, regex_l, "L1 N1 N2 10u", 10e-6)
        check_value(self, regex_l, "L2 N1 N2 10uH", 10e-6)
        check_value(self, regex_l, "L3 N1 N2 1U", 1e-6)
        check_value(self, regex_l, "L4 N1 N2 15mH", 0.015)
        check_value(self, regex_l, "LUN N1 N2 120nH", 120e-9)
        check_value(self, regex_l, "L55 N1 N2 12n", 12.0e-9)
        check_value(self, regex_l, "LA N1 N2 10.3E-9", 10.3e-9)
        check_value(self, regex_l, "LABC N1 N2 12e-12", 1e-12)
        check_value(self, regex_l, "LBCD N1 N2 {param*2+3}", "{param*2+3}")
        self.assertEqual(regex_l.match('LBCD N1 N2 {param*2+3}').group('nodes'), " N1 N2", "Tested Inductor Value")

    def test_diodes(self):
        regex_d = component_replace_regexs['D']
        self.assertIsNone(regex_d.match('X12 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('1N4148', regex_d.match('D1 N1 N2 1N4148').group('value'), "Tested Diode Value")
        self.assertEqual('D', regex_d.match('D1 N1 N2 D').group('value'), "Tested Diode Model")

    def test_bipolar(self):
        regex_q = component_replace_regexs['Q']
        self.assertIsNone(regex_q.match('X12 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('2N3904', regex_q.match('Q1 N1 N2 N3 2N3904').group('value'), "Tested Transistor Value")
        self.assertEqual('Q', regex_q.match('Q1 N1 N2 N3 Q').group('value'), "Tested Transistor Model")

    def test_mosfets(self):
        regex_m = component_replace_regexs['M']
        self.assertIsNone(regex_m.match('X12 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('IRF540', regex_m.match('M1 N1 N2 N3 N4 IRF540').group('value'), "Tested MOSFET Value")
        self.assertEqual('IRF540', regex_m.match('M1 N1 N2 N3 IRF540').group('value'), "Tested MOSFET Value")
        self.assertEqual('M', regex_m.match('M1 N1 N2 N3 N4 M').group('value'), "Tested MOSFET Model")

    def test_subcircuits(self):
        regex_x = component_replace_regexs['X']
        self.assertIsNone(regex_x.match('R1 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('SUB1', regex_x.match('X12 N1 N2 N3 SUB1').group('value'), "Tested Subcircuit Value")
        self.assertEqual('SUB1', regex_x.match('X12 N1 N2 N3 N4 SUB1 x=123 y=4u').group('value'), "Tested Subcircuit Value")
        self.assertEqual('x=123 y=4u', regex_x.match('X12 N1 N2 N3 N4 SUB1 x=123 y=4u').group('params'), "Tested Subcircuit Parameters")
        self.assertEqual(' N1 N2 N3 N4', regex_x.match('X12 N1 N2 N3 N4 SUB1 x=123 y=4u').group('nodes'), "Tested Subcircuit Ports")

    def test_independent_sources(self):
        regex_v = component_replace_regexs['V']
        self.assertIsNone(regex_v.match('R1 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('2 AC 1', regex_v.match('V1 NC_08 NC_09 2 AC 1 Rser=3').group('value'), "Tested Voltage Source Value")
        self.assertEqual(' Rser=3', regex_v.match('V1 NC_08 NC_09 2 AC 1 Rser=3').group('params'), "Tested Voltage Source Value")
        self.assertEqual('PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0)',
                         regex_v.match('V1 N1 N2 PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) Rser=3 Cpar=4').group('value'), "Tested Voltage Source Value")
        self.assertEqual(regex_v.match('V1 N001 0 5').group('value'), '5', "Tested Voltage Source Value")
        self.assertEqual(regex_v.match('V1 N1 N2 5').group('value'), '5', "Tested Voltage Source Value")
        self.assertEqual(regex_v.match('V1 N1 N2 5V').group('value'), '5V', "Tested Voltage Source Value")
        self.assertEqual(regex_v.match('V1 N1 N2 {param}').group('value'), '{param}', "Tested Voltage Source Value")

        regex_i = component_replace_regexs['I']
        self.assertEqual('2 AC 1', regex_i.match('I1 NC_08 NC_09 2 AC 1 Rser=3').group('value'), "Tested Independent Current Source Value")
        self.assertEqual(' Rser=3', regex_i.match('I1 NC_08 NC_09 2 AC 1 Rser=3').group('params'), "Tested Independent Current Source Value")
        self.assertEqual('PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0)',
                         regex_i.match('I1 N1 N2 PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) Rser=3 Cpar=4').group('value'), "Tested Voltage Source Value")
        self.assertEqual(regex_i.match('I1 N001 0 5').group('value'), '5', "Tested Independent Current Source Value")
        self.assertEqual(regex_i.match('I1 N1 N2 5').group('value'), '5', "Tested Independent Current Source Value")
        self.assertEqual(regex_i.match('I1 N1 N2 5V').group('value'), '5V', "Tested Independent Current Source Value")
        self.assertEqual(regex_i.match('I1 N1 N2 {param}').group('value'), '{param}', "Tested Independent Current Source Value")

    def test_subcircuits_edit(self):
        """Test subcircuits editing in the Spice Editor.
        The input is based on a top circuit plus a subcircuit that is not in a library.
        It uses the exact same tests as in test_asc_editor.py:test_subcircuits_edit():

        * Check the subcomponent list
        * test various methods of reading and changing the value of a component
          * get_component_value() on a compound component name
          * get_subcircuit().get_component_value()
          * get_component_floatvalue()
          * array access
            * value_str
            * value
        * adding extra parameters
        * writing to a new file
        """
        # It requires an input file in UTF-8, as otherwise the µ character is not recognized when doing equalFiles

        sc = "XX1"  # need an extra X here, as I'm in SpiceEditor, and not in AscEditor
        # load the file here, as this is somewhat tricky, and I don't want to block the other tests too early
        my_edt = spicelib.editor.spice_editor.SpiceEditor(test_dir + "top_circuit.net")

        self.assertEqual(my_edt.get_subcircuit(sc).get_components(), ['C1', 'X2', 'L1'], "Subcircuit component list")

        # START identical part with test_asc_editor.py:test_subcircuits_edit()
        self.assertEqual(my_edt.get_component_value(sc + ":L1"), "1µ", "Subcircuit Value for X1:L1, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "1µ", "Subcircuit Value for X1:L1, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 1e-6, msg="Subcircuit Value for X1:L1, float comparison")

        my_edt.set_component_value(sc + ":L1", 2e-6)  # set float value, on compound component name
        self.assertEqual(my_edt[sc + ":L1"].value_str, "2u", "Subcircuit Value_str for X1:L1, after 1st change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "2u", "Subcircuit Value for X1:L1, after 1st change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 2e-6, msg="Subcircuit Value for X1:L1, after 1st change, float comparison")
        self.check_update(my_edt, "XX1:L1", UpdateType.UpdateComponentValue, 2e-6)

        my_edt[sc + ":L1"].value = "3µH"  # set string value via compound method
        self.assertEqual(my_edt[sc + ":L1"].value_str, "3µH", "Subcircuit Value_str for X1:L1, after 2nd change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "3µH", "Subcircuit Value for X1:L1, after 2nd change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 3e-6, msg="Subcircuit Value for X1:L1, after 2nd change, float comparison")
        self.check_update(my_edt, "XX1:L1", UpdateType.UpdateComponentValue, "3µH")

        # now change the value to 4uH, because I don't want to deal with the µ character in equalFiles().
        my_edt.get_subcircuit(sc)["L1"].value = "4uH"  # set string value via indirect method
        self.assertEqual(my_edt[sc + ":L1"].value_str, "4uH", "Subcircuit Value_str for X1:L1, after 3rd change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "4uH", "Subcircuit Value for X1:L1, after 3rd change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 4e-6, msg="Subcircuit Value for X1:L1, after 3rd change, float comparison")
        self.check_update(my_edt, "XX1:L1", UpdateType.UpdateComponentValue, "4uH")

        my_edt[sc + ":C1"].value = 22e-9
        self.assertEqual(my_edt[sc + ":C1"].value_str, "22n", "Subcircuit Value_str for X1:C1, after change")
        self.assertAlmostEqual(my_edt.get_component_floatvalue(sc + ":C1"), 22e-9, msg="Subcircuit Value for X1:C1, after change")
        my_edt["R1"].value = 11
        my_edt.set_parameter("V1", "PULSE(0 1 1n 1n 1n {0.5/freq} {1/freq} 10)")
        my_edt.set_parameters(freq=1E6)
        my_edt.set_parameters(
            test_exiting_param_set1=24,
            test_exiting_param_set2=25,
            test_exiting_param_set3=26,
            test_exiting_param_set4=27,
            test_add_parameter=34.45, )
        # END identical part with test_asc_editor.py:test_subcircuits_edit()

        # Set component parameter
        my_edt.get_subcircuit(sc).set_component_parameters("C1", Rser=1)  # set string value via indirect method
        self.assertDictEqual(my_edt.get_subcircuit(sc).get_component_parameters("C1"), {"Rser": 1, 'Value': '22n'}, "Subcircuit parameters for X1:C1")
        my_edt.save_netlist(temp_dir + "top_circuit_edit.net")
        self.equalFiles(temp_dir + "top_circuit_edit.net", golden_dir + "top_circuit_edit.net")

        # Now will try to modify a component inside a sub-circuit inside a sub-circuit
        my_edt.set_component_value(sc + ":X2:R1", 50)
        my_edt.save_netlist(temp_dir + "top_circuit_edit1.net")
        self.equalFiles(temp_dir + "top_circuit_edit1.net", golden_dir + "top_circuit_edit1.net")
        my_edt[sc + ":X2:R1"].value = 99
        my_edt.save_netlist(temp_dir + "top_circuit_edit2.net")
        self.equalFiles(temp_dir + "top_circuit_edit2.net", golden_dir + "top_circuit_edit2.net")
        print("Updates:")
        for update in my_edt.netlist_updates:
            print(update)

    def test_semiconductor_edits(self):
        # inspecting W/L parameters
        params = self.edt3["XOPAMP:M11"].params
        print(params)
        self.assertAlmostEqual(2.5175e-05, params['W'])
        self.assertAlmostEqual(3.675e-06, params['L'])
        params = self.edt3["XOPAMP:M30"].params
        print(params)
        self.assertAlmostEqual(2.5175e-05, params['W'])
        self.assertAlmostEqual(3.675e-06, params['L'])
        self.assertEqual(22, params['M'])
        # updating channel length and width (twice width)
        actual_width = params['W']
        self.edt3["XOPAMP:M11"].params = dict(W=2 * actual_width)
        self.edt3["XOPAMP:M12"].set_params(L=4E-6)
        self.assertEqual(4, len(self.edt3.netlist_updates))
        self.check_update(self.edt3, "CLONE(PFC.SUB)", UpdateType.CloneSubcircuit, "PFC.SUB_XOPAMP", 0)
        self.check_update(self.edt3, "XOPAMP", UpdateType.UpdateComponentValue, "PFC.SUB_XOPAMP", 1)
        self.check_update(self.edt3, "XOPAMP:M11:W", UpdateType.UpdateComponentParameter, 2 * actual_width, 2)
        self.check_update(self.edt3, "XOPAMP:M12:L", UpdateType.UpdateComponentParameter, 4E-6, 3)
        updated_params = self.edt3["XOPAMP:M11"].params
        print(updated_params)
        self.assertAlmostEqual(2 * actual_width, updated_params['W'])
        self.edt3.save_netlist(temp_dir + "amp3_instance_edits.net")
        self.equalFiles(golden_dir + "amp3_instance_edits.net", temp_dir + "amp3_instance_edits.net")
        # Reverts all modifications
        self.edt3.reset_netlist()
        self.assertEqual(0, len(self.edt3.netlist_updates))
        opamp = self.edt3.get_subcircuit_named("PFC.SUB")
        # Updating the opamp
        opamp.set_component_parameters("M11", W=2 * actual_width)
        self.edt3.save_netlist(temp_dir + "amp3_subcircuit_edits.net")
        self.equalFiles(golden_dir + "amp3_subcircuit_edits.net", temp_dir + "amp3_subcircuit_edits.net")

    def test_elements(self):
        """Test reading and writing elements with the Editor.
        """
        my_netlist = "all_elements_lt.net"
        edt = spicelib.SpiceEditor(test_dir + my_netlist)
        # Check the element list for expected values and parameters
        # make sure there a few with 3 or more parameters
        expected = {
            "B1": ["V=1", {"tc1": 2}],
            "B2": ["V=V(1) < {Vlow} ? {Vlow} : V(1) > {Vhigh} ? {Vhigh} : V(1)", {"delay": 1}],
            "B3": ["I=cos(v(1))+sin(v(2))", {"ic": "1e-6,4", "delay": 10, "a": "b"}],
            "B4": ["R=V(1) < 0? 2 : 1", {}],
            "B5": ["B=V(NC_01)", {"VprXover": "50mV"}],
            #
            "C1": ["10µ", {"rser": 10, "c": "' with spaces '", "temp": 60}],
            "C2": ["10µF", {"tc1": 40}],
            "C3": ["'V(cc) < {Vt} ? {C1} : {Ch}'", {"tc1": -1e-03, "tc2": 1.3e-05}],
            "C4": ["1u*(4*atan(V(a,b)/4)*2+V(a,b))/3", {}],
            #
            "D1": ["1N914", {}],
            "D2": ["1N4001", {"m": 1, "n": 2, "a": 1e9}],
            #
            "E1": ["nc_09 nc_10 formula", {}],
            "E2": ["formula", {}],
            "F1": ["formula", {}],
            "G1": ["nc_15 nc_16 formula", {}],
            "G2": ["formula", {}],
            "H1": ["formula", {}],
            #
            "I1": ["1", {}],
            "I2": ["2 AC 1", {"c4": "\"bla bla\"", "Rser": 3, "bb": "aa"}],
            #
            "J1": ["2N3819", {}],
            "J2": ["2N3819", {"ic": "1,2", "temp": 6}],
            #
            "K1": ["1", {}],
            "K2": ["0.1", {}],
            #
            "L1": ["1", {"temp": 13}],
            "L2": ["1H", {}],
            "L3": ["\"V(cc) < {Vt} ? {L1} : {L2}\"", {"bb": "aa", "temp": 13}],
            #
            "M1": ["BSP89", {}],
            "M2": ["BSP89", {"temp": 2}],
            "M3": ["Si4410DY", {}],
            #
            "N1": ["BSIMBULK_osdi_P", {"as": "0.26235p", "ad": "0.26235p", "ps": "2.51u", "pd": "2.51u", "l": "0.1u", "w": "1u"}],
            # N2 is not mentioned on purpose, as it is identical to N1 and I want to see it unscathed at write time
            #
            "O1": ["LTRA", {}],
            #
            "P1": ["mname", {"LEN": 2}],
            "P2": ["12", {"port": 2, "Z0": 50}],  # 'DC' gets lost in translation
            #
            "Q1": ["2N2222", {}],
            "Q2": ["BC517", {"temp": 60, "ic": "0.6,5"}],
            #
            "R1": ["10k", {}],
            "R2": ["2k5r", {}],
            "R3": ["'V(cc) < {Vt} ? {R1} : {R2}'", {"temp": 13}],
            "R4": ["10k", {"tol": "1%", "pwr": 0.1}],
            #
            "S1": ["SW", {}],
            "T1": ["", {"Td": "50n", "Z0": 50}],
            #
            "U1": ["URC", {}],
            "U2": ["URC", {"len": 2}],
            #
            "V1": ["1", {}],
            "V2": ["PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) AC 1 2", {"Rser": 3, "Cpar": 4}],
            #
            "W1": ["W on", {}],
            #
            "XU1": ["a", {}],
            "XU2": ["AD549", {}],
            "XU3": ["level2", {"Avol": "1Meg", "GBW": "10Meg", "Slew": "10Meg", "Ilimit": "25m", "Rail": 0, "Vos": 0, "En": 0, "Enk": 0, "In": 0, "Ink": 0, "Rin": "500Meg"}],
            "XU4": ["OPAx189", {"bla_v2": "1%", "bla_sp1": 2, "bla_sp2": 3}],
            "XU5": ["OPAx189_float", {}],
            "XM1": ["{model_name}", {}],
            "XM2": ["nfet_06v0", {"l": "{XM1_l}", "w": "{XM1_w}", "nf": 1, "ad": "'int((nf+1)/2) * W/nf * 0.18u'", "as": "'int((nf+2)/2) * W/nf * 0.18u'", "pd": "'2*int((nf+1)/2) * (W/nf + 0.18u)'", "ps": "'2*int((nf+2)/2) * (W/nf + 0.18u)'", "nrd": "'0.18u / W'", "nrs": "'0.18u / W'", "sa": 0, "sb": 0, "sd": 0, "m": 1}],

            #
            "Y1": ["ymod", {"LEN": 2}],
            "Y2": ["1e8", {"q": 10}],
            #
            "Z1": ["NMF", {}],
            "Z2": ["NMF", {"ic": "1,2", "area": 1.4}],
            #
            "Ã1": ["TYPE", {"I": 5}],
            "¥1": ["TYPE", {"I": 5}],
            "×1": ["", {"turns": "1 .5 .5"}],
            "×2": ["", {"turns": "1 .5 .5 .5", "L": 2}]
        }
        # print(f"components: {edt.get_components()}")
        for el, exp in expected.items():
            # print(f"Reading {el}")
            value = exp[0]
            self.assertEqual(edt.get_component_value(el).casefold(), value.casefold(), f"Test reading {el} Value")
            params = edt.get_component_parameters(el)
            self.assertDictEqual(params, params | exp[1], f"Test reading {el} Parameters")
        
        new_value_default = "1e-9"
        new_values = {
            "B": "V=1e-9"
        }
        new_param = {"blabla": "1 2 3 4 5 6 7"}
        new_param_value = 1e-9
        seq = 0  
        for el, exp in expected.items():
            value = exp[0]
            params = dict(sorted(exp[1].items()))  # sort the parameters, so that we can always get the same ones
            new_value = new_value_default
            # modify value
            if len(value) > 0:
                if el[0] in new_values.keys():
                    new_value = new_values[el[0]]
                # print(f"Modifying {el}")
                edt.set_component_value(el, new_value)
                self.assertEqual(edt.get_component_value(el).casefold(), new_value.casefold(), f"Test reading back {el} Value")
            # modfy parameter
            if len(params) >= 3:
                # get the nth parameter (there must be more efficient ways, but this is simple)
                my_nr = 0
                my_change_key = None
                my_del_key = None
                for k, v in params.items():
                    if my_nr == seq:
                        my_change_key = k
                    if my_nr == (seq + 1) % 3:
                        my_del_key = k
                    my_nr += 1
                    if my_nr >= 3:
                        break
                # print(f"Modifying parameter '{my_change_key}' (nr {seq}) from {el} parameters, to {new_param_value}")
                edt.set_component_parameters(el, **{my_change_key: new_param_value})
                # adapt my expected value
                exp[1][my_change_key] = new_param_value
                seq += 1
                if seq >= 3:
                    seq = 1
                params = edt.get_component_parameters(el)
                self.assertEqual(params, params | exp[1], f"Test reading {el} Parameters after change existing parameter")
                # add new parameter
                # print(f"Adding parameter {new_param} to {el} parameters")
                edt.set_component_parameters(el, **new_param)
                exp[1].update(new_param)
                params = edt.get_component_parameters(el)
                self.assertEqual(params, params | exp[1], f"Test reading {el} Parameters after adding parameter")
                # remove n+1th parameter
                # print(f"Deleting parameter '{my_del_key}' from {el} parameters")
                edt.set_component_parameters(el, **{my_del_key: None})
                del exp[1][my_del_key]
                params = edt.get_component_parameters(el)
                self.assertEqual(params, params | exp[1], f"Test reading {el} Parameters after deleting parameter")
                
        # save file, compare
        edt.save_netlist(temp_dir + my_netlist)
        self.equalFiles(temp_dir + my_netlist, golden_dir + my_netlist)
            

if __name__ == '__main__':
    unittest.main()
    # runner = unittest.TextTestRunner(verbosity=2)
    # runner.run(SpiceEditor_Test("test_elements"))
