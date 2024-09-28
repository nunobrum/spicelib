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
        r1 = self.edt['R1']
        self.assertEqual('10k', r1.value_str, "Tested R1 Value")  # add assertion here
        self.assertListEqual(['Vin', 'R1', 'R2', 'D1'], self.edt.get_components(), "Tested get_components")  # add assertion here
        r1.value = 33000
        self.edt.save_netlist(temp_dir + 'test_components_output.asc')
        self.equalFiles(temp_dir + 'test_components_output.asc', golden_dir + 'test_components_output.asc')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.assertEqual(r1.value_str, '33k', "Tested R1 Value")  # add assertion here
        r1.set_params(Tc1='0', Tc2='0', pwr=None)
        # self.edt.set_component_parameters('R1', Tc1='0', Tc2='0', pwr=None)
        self.edt.save_netlist(temp_dir + 'test_components_output_2.asc')
        self.equalFiles(temp_dir + 'test_components_output_2.asc', golden_dir + 'test_components_output_2.asc')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
            self.assertEqual(r1.params[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.edt.save_netlist(temp_dir + 'test_components_output_1.asc')
        self.equalFiles(temp_dir + 'test_components_output_1.asc', golden_dir + 'test_components_output_1.asc')

    def test_component_legacy_editing(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10k', "Tested R1 Value")  # add assertion here
        self.assertListEqual(self.edt.get_components(), ['Vin', 'R1', 'R2', 'D1'], "Tested get_components")  # add assertion here
        self.edt.set_component_value('R1', '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.asc')
        self.equalFiles(temp_dir + 'test_components_output.asc', golden_dir + 'test_components_output.asc')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.edt.set_component_parameters('R1', Tc1='0', Tc2='0', pwr=None)
        self.edt.save_netlist(temp_dir + 'test_components_output_2.asc')
        self.equalFiles(temp_dir + 'test_components_output_2.asc', golden_dir + 'test_components_output_2.asc')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': 0, 'Tc2': 0}.items():
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

    def test_subcircuit1_edit(self):
        edt2 = spicelib.editor.asc_editor.AscEditor(test_dir + "top_circuit.asc")
        self.assertEqual(edt2.get_subcircuit('X1').get_components(), ['C1', 'C2', 'L1'], "Subcircuit component list")
        self.assertEqual(edt2.get_component_value("X1:L1"), "1µ", "Subcircuit Value for X1:L1, direct")
        self.assertEqual(edt2.get_subcircuit('X1').get_component_value('L1'), "1µ", "Subcircuit Value for X1:L1, indirect")
        edt2.set_component_value("X1:L1", 2e-6)
        self.assertEqual(edt2['X1:L1'].value_str, "2u", "Subcircuit Value for X1:L1, after change")
        edt2['R1'].value = 11
        edt2.set_parameter("V1", "PULSE(0 1 1n 1n 1n {0.5/freq} {1/freq} 10)")
        edt2.set_parameters(freq=1E6)
        edt2["X1:L1"].value = '1µH'
        print(f"X1:L1: {edt2['X1:L1'].value_str}")
        print(f"X1:L1: {edt2['X1:L1'].value}")
        edt2["X1:C1"].value = 22e-9
        print(f"X1:C1: {edt2['X1:C1'].value_str}")
        print(f"X1:C2: {edt2.get_component_floatvalue('X1:C2')}")
        print(f"R2: {edt2['R2'].value_str}")
        edt2.set_parameters(
            test_exiting_param_set1=24,
            test_exiting_param_set2=25,
            test_exiting_param_set3=26,
            test_exiting_param_set4=27,
            test_add_parameter=34.45, )
        S = edt2.get_subcircuit('X1')
        S.asc_file_path = temp_dir + "subcircuit_edit.asc"  # Only for test purposes
        edt2.save_netlist(temp_dir + "top_circuit_edit.asc")
        self.equalFiles(temp_dir + "top_circuit_edit.asc", golden_dir + "top_circuit_edit.asc")
        
# E = AscEditor('testfiles\\top_circuit.asc')
# print(E.get_components())
# print(E.get_components('R'))
# print(E.get_subcircuit('X1').get_components())
# E.set_component_value("X1:L1", 2e-6)
# print(E['R1'].value)
# print("Setting R1 to 10k")
# E['R1'].value = 11
# print("Setting parameter I1 1.23k")
# E.set_parameter("V1", "PULSE(0 1 1n 1n 1n {0.5/freq} {1/freq} 10)")
# print(E.get_parameter('V1'))
# print("Setting frequency to 1MHz")
# E.set_parameters(freq=1E6)
# print("Setting XX1:L1 to 1µH")
# E["X1:L1"].value = '1µH'
# print("Setting XX1:C1 to 22nF")
# E["X1:C1"].value = 22e-9
# print("Setting XX1:C2 to 120nF")
# E["X1:C2"].value = '120n'
# print(E["X1:C1"].value)
# print(E.get_component_floatvalue("X1:C2"))
# print(E["X1:L1"].value)
# print(E["R2"].value_str)
# E.set_parameters(
#     test_exiting_param_set1=24,
#     test_exiting_param_set2=25,
#     test_exiting_param_set3=26,
#     test_exiting_param_set4=27,
#     test_add_parameter=34.45, )
# S = E.get_subcircuit('X1')
# S.asc_file_path = "testfiles\\subcircuit_edit.asc" # Only for test purposes
# E.save_netlist("testfiles\\top_circuit_edit.asc")

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
