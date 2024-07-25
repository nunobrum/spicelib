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

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)

class SpiceEditor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.editor.spice_editor.SpiceEditor(test_dir + "DC sweep.net")
        self.edt2 = spicelib.editor.spice_editor.SpiceEditor(test_dir + "opamptest.net")

    def test_component_editing_1(self):
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
        
    def test_component_editing_2(self):
        self.assertEqual(self.edt2.get_component_value('V1'), '15', "Tested V1 Value")
        self.assertEqual(self.edt2.get_component_value('V3'), 'PWL(1u 0 +2n 1 +1m 1 +2n 0 +1m 0 +2n -1 +1m -1 +2n 0) AC 1', "Tested V3 Value")  # complex value, with parameters
        self.assertEqual(self.edt2.get_component_value('XU1'), 'level2', "Tested U1 Value")  # has parameters
        self.assertEqual(self.edt2.get_component_parameters('XU1')['Rin'], '501Meg', "Tested U1 Rin Value") # last in the list
        self.assertEqual(self.edt2.get_component_value('XU2'), 'AD549', "Tested U2 Value")  # no parameters
        self.assertListEqual(self.edt2.get_components(), ['V1', 'V2', 'V3', 'XU1', 'XU2'], "Tested get_components")
        self.edt2.set_component_value('V3', 'PWL(2u 0 +1p 1 +1m 1)')
        self.edt2.set_component_parameters('V3', Rser=1)  # first in the list
        self.edt2.set_component_value('XU1', 'level3')
        self.edt2.set_component_parameters('XU1', GBW='1Meg')  # somewhere in the list
        self.edt2.save_netlist(temp_dir + 'opamptest_output_1.net')
        self.equalFiles(temp_dir + 'opamptest_output_1.net', golden_dir + 'opamptest_output_1.net')

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


if __name__ == '__main__':
    unittest.main()
