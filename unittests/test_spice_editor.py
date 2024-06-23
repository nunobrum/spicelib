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
from spicelib.editor.base_editor import parse_value

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)

class SpiceEditor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.editor.spice_editor.SpiceEditor(test_dir + "DC sweep.net")

    def test_component_editing(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10k', "Tested R1 Value")  # add assertion here
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")  # add assertion here
        self.edt.set_component_value('R1', '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.net')
        self.equalFiles(temp_dir + 'test_components_output.net', golden_dir + 'test_components_output.net')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.edt.set_component_parameters('R1', Tc1=0, Tc2=0, pwr=None)
        self.edt.save_netlist(temp_dir + 'test_components_output_2.net')
        self.equalFiles(temp_dir + 'test_components_output_2.net', golden_dir + 'test_components_output_2.net')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
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

    def test_regexes(self):
        """Validates the RegEx expressions on the Spice Editor file"""
        from spicelib.editor.spice_editor import component_replace_regexs
        from spicelib.editor.base_editor import scan_eng
        # Resistors
        regex_r = component_replace_regexs['R']
        self.assertIsNone(regex_r.match('X12 N1 N2 10k'), "Invalid prefix")

        def check_value(regex, line, value, msg=None):
            r = regex_r.match(line)
            self.assertIsNotNone(r, "Accepted regex")
            value_str = r.group('value')
            if isinstance(value, str):
                value_test = value_str
            else:
                value_test = parse_value(value_str)
            if msg:
                self.assertEqual(value_test, value, msg)
            else:
                self.assertEqual(value_test, value, f"Pass {value} for {line}")

        check_value(regex_r, "Rq N1 N2 10k", '10k')
        check_value(regex_r, "Rq N1 N2 10R3", 10.3)
        check_value(regex_r, "Rq N1 N2 10k5", 10500)
        check_value(regex_r, "Rq N1 N2 10K6", 10600)
        check_value(regex_r, "Rq N1 N2 11Meg", 11E6)
        check_value(regex_r, "Rq N1 N2 10Meg5", 10.5e6)
        check_value(regex_r, "Rq N1 N2 {param1 + Param2}", "{param1 + Param2}")


if __name__ == '__main__':
    unittest.main()
