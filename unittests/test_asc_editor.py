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
# Name:        test_asc_editor.py
# Purpose:     Tool used validate the LTSpice ASC Files Editor
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

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)

class ASC_Editor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.editor.asc_editor.AscEditor(test_dir + "DC sweep.asc")

    def test_component_editing(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10k', "Tested R1 Value")  # add assertion here
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")  # add assertion here
        self.edt.set_component_value('R1', '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.asc')
        self.equalFiles(temp_dir + 'test_components_output.asc', golden_dir + 'test_components_output.asc')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.edt.set_component_parameters('R1', Tc1='0', Tc2='0')
        self.edt.save_netlist(temp_dir + 'test_components_output_2.asc')
        self.equalFiles(temp_dir + 'test_components_output_2.asc', golden_dir + 'test_components_output_2.asc')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'pwr': 0.1, 'tol': '1%'}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.edt.save_netlist(temp_dir + 'test_components_output_1.asc')
        self.equalFiles(temp_dir + 'test_components_output_1.asc', golden_dir + 'test_components_output_1.asc')

    def test_parameter_edit(self):
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameter('TEMP', 25)
        self.assertEqual(self.edt.get_parameter('TEMP'), '25', "Tested TEMP Parameter")  # add assertion here
        self.edt.save_netlist(temp_dir + 'test_parameter_output.asc')
        self.equalFiles(temp_dir + 'test_parameter_output.asc', golden_dir + 'test_parameter_output.asc')
        self.edt.set_parameter('TEMP', 0)  # reset to 0
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here

    def test_instructions(self):
        self.edt.add_instruction('.ac dec 10 1 100k')
        self.edt.add_instruction('.save V(vout)')
        self.edt.add_instruction('.save I(R1)')
        self.edt.add_instruction('.save I(R2)')
        self.edt.add_instruction('.save I(D1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output.asc')
        self.equalFiles(temp_dir + 'test_instructions_output.asc', golden_dir + 'test_instructions_output.asc')
        self.edt.remove_instruction('.save I(R1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_1.asc')
        self.equalFiles(temp_dir + 'test_instructions_output_1.asc', golden_dir + 'test_instructions_output_1.asc')
        self.edt.remove_Xinstruction(r"\.save\sI\(.*\)")  # removes all .save instructions for currents
        self.edt.save_netlist(temp_dir + 'test_instructions_output_2.asc')
        self.equalFiles(temp_dir + 'test_instructions_output_2.asc', golden_dir + 'test_instructions_output_2.asc')

    def equalFiles(self, file1, file2):
        with open(file1, 'r') as f1:
            lines1 = f1.readlines()
        with open(file2, 'r') as f2:
            lines2 = f2.readlines()
        self.assertEqual(len(lines1), len(lines2), "Number of lines is different")
        for i, lines in enumerate(zip(lines1, lines2)):
            self.assertEqual(lines[0], lines[1], "Line %d" % i)


if __name__ == '__main__':
    unittest.main()
