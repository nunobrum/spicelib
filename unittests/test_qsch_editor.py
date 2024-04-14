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


def equalFiles(testcase, file1, file2):
    with open(file1, 'r', encoding='cp1252') as f1:
        lines1 = f1.readlines()
    with open(file2, 'r', encoding='cp1252') as f2:
        lines2 = f2.readlines()
    testcase.assertEqual(len(lines1), len(lines2), "Files have different number of lines")
    for i in range(len(lines1)):
        data1 = lines1[i].strip()  # Remove white spaces and line terminators
        data2 = lines2[i].strip()
        if data1.startswith('*') and data2.startswith('*'):
            continue  # Skip comments
        testcase.assertEqual(data1, data2, f"Files \"{file1}\" and \"{file2}\" are not equal")
    

class ASC_Editor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "DC sweep.qsch")

    def test_component_editing(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10K', "Tested R1 Value")  # add assertion here
        self.assertSetEqual(set(self.edt.get_components()), set(('Vin', 'R1', 'R2', 'D1')), "Tested get_components")  # add assertion here
        self.edt.set_component_value('R1', '33K')
        self.edt.save_netlist(temp_dir + 'test_components_output.qsch')
        equalFiles(self, temp_dir + 'test_components_output.qsch', golden_dir + 'test_components_output.qsch')
        self.assertEqual(self.edt.get_component_value('R1'), '33K', "Tested R1 Value")  # add assertion here
        self.edt.remove_component('R1')
        self.edt.save_netlist(temp_dir + 'test_components_output_1.qsch')
        equalFiles(self, temp_dir + 'test_components_output_1.qsch', golden_dir + 'test_components_output_1.qsch')

    def test_parameter_edit(self):
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameter('TEMP', 25)
        self.assertEqual(self.edt.get_parameter('TEMP'), '25', "Tested TEMP Parameter")  # add assertion here
        self.edt.save_netlist(temp_dir + 'test_parameter_output.qsch')
        equalFiles(self, temp_dir + 'test_parameter_output.qsch', golden_dir + 'test_parameter_output.qsch')
        self.edt.set_parameter('TEMP', 0)  # reset to 0
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here

    def test_instructions(self):
        self.edt.add_instruction('.ac dec 10 1 100K')
        self.edt.add_instruction('.save V(vout)')
        self.edt.add_instruction('.save I(R1)')
        self.edt.add_instruction('.save I(R2)')
        self.edt.add_instruction('.save I(D1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output.qsch', golden_dir + 'test_instructions_output.qsch')
        self.edt.remove_instruction('.save I(R1)')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_1.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output_1.qsch', golden_dir + 'test_instructions_output_1.qsch')
        self.edt.remove_Xinstruction(r"\.save\sI\(.*\)")  # removes all .save instructions for currents
        self.edt.save_netlist(temp_dir + 'test_instructions_output_2.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output_2.qsch', golden_dir + 'test_instructions_output_2.qsch')


class QschEditorRotation(unittest.TestCase):

    def test_component_rotations(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "qsch_rotation.qsch")
        self.edt.save_netlist(temp_dir + 'qsch_rotation.net')
        equalFiles(self, temp_dir + 'qsch_rotation.net', golden_dir + "qsch_rotation.net")
        self.qsch = spicelib.editor.qsch_editor.QschEditor(test_dir + 'qsch_rotation_set_test.qsch')
        for rotation in range(0, 360, 45):
            self.qsch.set_component_position('R1', (0, 0), rotation)
            self.qsch.save_netlist(temp_dir + f'qsch_rotation_set_{rotation}.qsch')
            equalFiles(self, temp_dir + f'qsch_rotation_set_{rotation}.qsch', golden_dir + f"qsch_rotation_set_{rotation}.qsch")


class QschEditorSpiceGeneration(unittest.TestCase):

    def test_hierarchical(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "top_circuit.qsch")
        self.edt.save_netlist(temp_dir + "top_circuit.net")
        equalFiles(self, temp_dir + 'top_circuit.net', golden_dir + "top_circuit.net")


if __name__ == '__main__':
    unittest.main()
