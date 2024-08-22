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
import re
import sys
import unittest

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path

import spicelib
from spicelib.editor.base_editor import to_float
from spicelib.editor.spice_editor import component_replace_regexs

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
        self.edt = spicelib.editor.spice_editor.SpiceEditor(test_dir + "DC sweep.net")

    def test_component_editing(self):
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")
        r1 = self.edt['R1']
        self.assertEqual(r1.value_str, '10k', "Tested R1 Value")
        self.assertEqual(r1.value, 10000, "Tested R1 Numeric Value")
        self.assertListEqual(r1.ports, ['in', 'out'], "Tested R1 Nodes")
        r1.value = '33k'
        self.assertEqual(r1.value_str, '33k', "Tested R1 Value")
        self.edt.save_netlist(temp_dir + 'test_components_output.net')
        self.equalFiles(temp_dir + 'test_components_output.net', golden_dir + 'test_components_output.net')
        self.assertEqual(self.edt['R1'].value_str, '33k', "Tested R1 Value")
        r1['Tc1'] = 0
        r1['Tc2'] = 0
        r1['pwr'] =None
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

    def test_parameter_edit(self):
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameter('TEMP', 25)
        self.assertEqual(self.edt.get_parameter('TEMP'), '25', "Tested TEMP Parameter")  # add assertion here
        self.edt.save_netlist(temp_dir + 'test_parameter_output.net')
        self.equalFiles(temp_dir + 'test_parameter_output.net', golden_dir + 'test_parameter_output.net')
        self.edt.set_parameter('TEMP', 0)  # reset to 0
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here

    def test_instructions(self):
        self.edt.add_instruction('.ac dec 10 1 100k')
        self.edt.add_instruction('.save V(vout)')
        self.edt.add_instruction('.save I(R1)')
        self.edt.add_instruction('.save I(R2)')
        self.edt.add_instruction('.save I(D1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output.net')
        self.equalFiles(temp_dir + 'test_instructions_output.net', golden_dir + 'test_instructions_output.net')
        self.edt.remove_instruction('.save I(R1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_1.net')
        self.equalFiles(temp_dir + 'test_instructions_output_1.net', golden_dir + 'test_instructions_output_1.net')
        self.edt.remove_Xinstruction(r"\.save\sI\(.*\)")  # removes all .save instructions for currents
        self.edt.save_netlist(temp_dir + 'test_instructions_output_2.net')
        self.equalFiles(temp_dir + 'test_instructions_output_2.net', golden_dir + 'test_instructions_output_2.net')

    def equalFiles(self, file1, file2):
        with open(file1, 'r') as f1:
            lines1 = f1.readlines()
        with open(file2, 'r') as f2:
            lines2 = f2.readlines()
        self.assertEqual(len(lines1), len(lines2), "Files have different number of lines")
        for i, lines in enumerate(zip(lines1, lines2)):
            self.assertEqual(lines[0], lines[1], "Line %d" % i)

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
        self.assertEqual(regex_l.match('LBCD N1 N2 {param*2+3}').group('nodes'), " N1 N2",  "Tested Inductor Value")

    def test_diodes(self):
        regex_d = component_replace_regexs['D']
        self.assertIsNone(regex_d.match('X12 N1 N2 10k'), "Invalid prefix")
        self.assertEqual('1N4148',regex_d.match('D1 N1 N2 1N4148').group('value'),  "Tested Diode Value")
        self.assertEqual('D', regex_d.match('D1 N1 N2 D').group('value'),  "Tested Diode Model")

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
        self.assertEqual(' x=123 y=4u', regex_x.match('X12 N1 N2 N3 N4 SUB1 x=123 y=4u').group('params'), "Tested Subcircuit Parameters")
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

    def test_legacy_approach(self):
        """Tests accessing components as an object."""
        self.assertEqual(10000, self.edt.get_component_floatvalue('R1'), "Component value is as expected.")
        self.assertEqual('10k', self.edt.get_component_value('R1'), "Access to raw attributes")
        self.assertListEqual(['Vin', 'R1', 'R2', 'D1'], self.edt.get_components(),
                             "Tested get_components")  # add assertion here
        self.assertListEqual(['in', 'out'], self.edt.get_component_nodes('R1'), "Tested R1 Nodes")
        self.edt.set_component_value('R1', '33k')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")
        self.edt.save_netlist(temp_dir + 'test_components_output.net')
        self.equalFiles(temp_dir + 'test_components_output.net', golden_dir + 'test_components_output.net')
        self.assertEqual('33k', self.edt.get_component_value('R1'), "Tested R1 Value")
        self.edt.set_component_parameters('R1', Tc1=0, Tc2=0, pwr=None)
        self.assertEqual(self.edt.get_component_parameters('R1')['Tc1'], 0, "Tested R1 Tc1 Parameter")
        self.assertEqual(self.edt.get_component_parameters('R1')['Tc2'], 0, "Tested R1 Tc2 Parameter")
        self.edt.save_netlist(temp_dir + 'test_components_output_2.net')
        self.equalFiles(temp_dir + 'test_components_output_2.net', golden_dir + 'test_components_output_2.net')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.edt.save_netlist(temp_dir + 'test_components_output_1.net')
        self.equalFiles(temp_dir + 'test_components_output_1.net', golden_dir + 'test_components_output_1.net')


if __name__ == '__main__':
    unittest.main()
