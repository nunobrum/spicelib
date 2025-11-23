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
import logging
import io

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path

import spicelib
from spicelib.editor.updates import UpdateType

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)


# set the logger to print to console and at info level
spicelib.set_log_level(logging.INFO)


def equalFiles(testcase, file1, file2):
    with open(file1, 'r', encoding='cp1252') as f1:
        lines1 = f1.readlines()
    with open(file2, 'r', encoding='cp1252') as f2:
        lines2 = f2.readlines()
    testcase.assertEqual(len(lines1), len(lines2), f"Files \"{file1}\" and \"{file2}\" have different number of lines")
    for i in range(len(lines1)):
        data1 = lines1[i].strip()  # Remove white spaces and line terminators
        data2 = lines2[i].strip()
        if data1.startswith('*') and data2.startswith('*'):
            continue  # Skip comments
        elif data1.startswith('.lib') and data2.startswith('.lib'):
            continue  # Skip library definitions
        testcase.assertEqual(data1, data2, f"Files \"{file1}\" and \"{file2}\" are not equal")
    

class ASC_Editor_Test(unittest.TestCase):

    def setUp(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "DC sweep.qsch")

    def check_update(self, name, update, value=None, index=-1):
        self.assertEqual(name, self.edt.netlist_updates[index].name, "Name mismatch")
        self.assertEqual(update, self.edt.netlist_updates[index].updates, "Update Type mismatch")
        if update not in (UpdateType.DeleteParameter, UpdateType.DeleteComponent, UpdateType.DeleteComponentParameter):
            self.assertEqual(value, self.edt.netlist_updates[index].value, "Value mismatch")

    def test_component_editing(self):
        self.assertEqual(self.edt.get_component_value('R1'), '10K', "Tested R1 Value")  # add assertion here
        self.assertSetEqual(set(self.edt.get_components()), set(('Vin', 'R1', 'R2', 'D1')), "Tested get_components")  # add assertion here
        self.edt.set_component_value('R1', '33k')
        self.check_update('R1', UpdateType.UpdateComponentValue, '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output.qsch')
        equalFiles(self, temp_dir + 'test_components_output.qsch', golden_dir + 'test_components_output.qsch')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.edt.set_component_parameters('R1', Tc1=0, Tc2=0)
        self.check_update('R1:Tc1', UpdateType.UpdateComponentParameter, 0, -2)
        self.check_update('R1:Tc2', UpdateType.UpdateComponentParameter, 0, -1)
        self.edt.save_netlist(temp_dir + 'test_components_output_2.qsch')
        equalFiles(self, temp_dir + 'test_components_output_2.qsch', golden_dir + 'test_components_output_2.qsch')
        r1_params = self.edt.get_component_parameters('R1')
        for key, value in {'Tc1': '0', 'Tc2': '0'}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")
        self.edt.remove_component('R1')
        self.check_update('R1', UpdateType.DeleteComponent)
        self.edt.save_netlist(temp_dir + 'test_components_output_1.qsch')
        equalFiles(self, temp_dir + 'test_components_output_1.qsch', golden_dir + 'test_components_output_1.qsch')

    def test_component_editing_obj(self):
        r1 = self.edt['R1']
        self.assertEqual(r1.value_str, '10K', "Tested R1 Value")  # add assertion here
        r1.value = 33000
        self.check_update('R1', UpdateType.UpdateComponentValue, '33k')
        self.edt.save_netlist(temp_dir + 'test_components_output_obj.qsch')
        equalFiles(self, temp_dir + 'test_components_output_obj.qsch', golden_dir + 'test_components_output_obj.qsch')
        self.assertEqual(self.edt.get_component_value('R1'), '33k', "Tested R1 Value")  # add assertion here
        self.assertEqual(r1.value_str, '33k', "Tested R1 Value")
        r1.set_params(Tc1='0', Tc2='0', pwr=None)
        self.check_update('R1:Tc1', UpdateType.UpdateComponentParameter, '0', -3)
        self.check_update('R1:Tc2', UpdateType.UpdateComponentParameter, '0', -2)
        self.check_update('R1:pwr', UpdateType.DeleteComponentParameter, None, -1)
        self.edt.save_netlist(temp_dir + 'test_components_output_2_obj.qsch')
        equalFiles(self, temp_dir + 'test_components_output_2_obj.qsch', golden_dir + 'test_components_output_2_obj.qsch')
        r1_params = r1.params
        for key, value in {'Tc1': '0', 'Tc2': '0'}.items():
            self.assertEqual(r1_params[key], value, f"Tested R1 {key} Parameter")

    def test_parameter_edit(self):
        self.assertEqual(self.edt.get_all_parameter_names(), ['RES', 'TEMP'])        
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameter('TEMP', 25)
        self.check_update('TEMP', UpdateType.UpdateParameter, 25)
        self.assertEqual(self.edt.get_parameter('TEMP'), '25', "Tested TEMP Parameter")  # add assertion here
        self.edt.set_parameters(new_param=120, other_param="voila")
        self.check_update("new_param", UpdateType.UpdateParameter, 120, -2)
        self.check_update("other_param", UpdateType.UpdateParameter, "voila", -1)
        self.edt.save_as(temp_dir + 'test_parameter_output.qsch')
        equalFiles(self, golden_dir + 'test_parameter_output.qsch', temp_dir + 'test_parameter_output.qsch')
        self.edt.save_netlist(temp_dir + 'test_parameter_output_qsch.net')
        equalFiles(self, golden_dir + 'test_parameter_output_qsch.net', temp_dir + 'test_parameter_output_qsch.net')
        update_size = len(self.edt.netlist_updates)
        self.edt.set_parameter('TEMP', 0)  # reset to 0
        self.check_update('TEMP', UpdateType.UpdateParameter, 0, 0)
        self.assertEqual(update_size, len(self.edt.netlist_updates), "The number of updates was not changed")
        self.edt.set_parameter('other_param', "Pronto")
        self.check_update('other_param', UpdateType.UpdateParameter, "Pronto")
        self.assertEqual(self.edt.get_parameter('TEMP'), '0', "Tested TEMP Parameter")  # add assertion here
        self.edt.save_as(temp_dir + 'test_parameter_output1.qsch')
        equalFiles(self, golden_dir + 'test_parameter_output1.qsch', temp_dir + 'test_parameter_output1.qsch')
        self.edt.save_netlist(temp_dir + 'test_parameter_output1.net')
        equalFiles(self, golden_dir + 'test_parameter_output1.net', temp_dir + 'test_parameter_output1.net')

    def test_instructions(self):
        self.edt.add_instruction('.ac dec 10 1 100K')
        self.edt.add_instruction('.save V(vout)')
        self.edt.add_instruction('.save I(R1)')
        self.edt.add_instruction('.save I(R2)')
        self.edt.add_instruction('.save I(D1)')
        self.check_update("INSTRUCTION", UpdateType.DeleteInstruction, ".dc Vin 1 10 9", 0)
        self.check_update("INSTRUCTION", UpdateType.AddInstruction, ".ac dec 10 1 100K", 1)
        self.check_update("INSTRUCTION", UpdateType.AddInstruction, ".save V(vout)", 2)
        self.check_update("INSTRUCTION", UpdateType.AddInstruction, ".save I(R1)", 3)
        self.check_update("INSTRUCTION", UpdateType.AddInstruction, ".save I(R2)", 4)
        self.check_update("INSTRUCTION", UpdateType.AddInstruction, ".save I(D1)", 5)
        self.edt.save_as(temp_dir + 'test_instructions_output.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output.qsch', golden_dir + 'test_instructions_output.qsch')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_qsch.net')
        equalFiles(self, temp_dir + 'test_instructions_output_qsch.net', golden_dir + 'test_instructions_output_qsch.net')
        self.edt.remove_instruction('.save I(R1)')
        self.check_update("INSTRUCTION", UpdateType.DeleteInstruction, '.save I(R1)')
        self.edt.save_as(temp_dir + 'test_instructions_output_1.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output_1.qsch', golden_dir + 'test_instructions_output_1.qsch')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_qsch_1.net')
        equalFiles(self, temp_dir + 'test_instructions_output_qsch_1.net', golden_dir + 'test_instructions_output_qsch_1.net')
        self.edt.remove_Xinstruction(r"\.save\sI\(.*\)")  # removes all .save instructions for currents
        self.check_update("INSTRUCTION", UpdateType.DeleteInstruction, '.save I(R2)', -2)
        self.check_update("INSTRUCTION", UpdateType.DeleteInstruction, '.save I(D1)', -1)
        self.edt.save_as(temp_dir + 'test_instructions_output_2.qsch')
        equalFiles(self, temp_dir + 'test_instructions_output_2.qsch', golden_dir + 'test_instructions_output_2.qsch')
        self.edt.save_netlist(temp_dir + 'test_instructions_output_qsch_2.net')
        equalFiles(self, temp_dir + 'test_instructions_output_qsch_2.net', golden_dir + 'test_instructions_output_qsch_2.net')
        # Test storing netlists in StringIO
        buffer=io.StringIO()
        self.edt.save_netlist(buffer)
        buffer.seek(0)
        with open(temp_dir + 'test_instructions_output_qsch_2_StringIO.net', 'w') as f:
            for line in buffer:
                f.write(line)
        equalFiles(self, temp_dir + 'test_instructions_output_qsch_2_StringIO.net', golden_dir + 'test_instructions_output_qsch_2.net')
        
    def test_comments(self):
        myfile = "comment_test.qsch"
        my_edt = spicelib.editor.qsch_editor.QschEditor(test_dir + myfile)

        self.assertEqual(my_edt.get_all_parameter_names(), ["R"])
        my_edt.add_instruction(".ac test")  # OK
        my_edt.add_instruction(".option blabla")  # OK
        my_edt.remove_instruction(".option SavePowers")  # OK
        my_edt.remove_Xinstruction(r"\.model.*")  # OK
        my_edt.set_parameter("R", 1e6)  # OK
        
        my_edt.save_netlist(temp_dir + myfile)
        equalFiles(self, temp_dir + myfile, golden_dir + myfile)


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
        if sys.platform.startswith("win"):
            equalFiles(self, temp_dir + 'top_circuit.net', golden_dir + "top_circuit_win32.net")
        else:
            equalFiles(self, temp_dir + 'top_circuit.net', golden_dir + "top_circuit.net")

    def test_all_elements(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "all_elements.qsch")
        counter_config = {"X1": ["in,b", "in,b", "in,uc", "out,uc", "out,b"]}
        self.edt.save_netlist(temp_dir + "all_elements.net", counter_config)
        equalFiles(self, temp_dir + 'all_elements.net', golden_dir + "all_elements.net")


class QschEditorFromAscConversion(unittest.TestCase):

    def test_asc_to_qsch(self):
        from spicelib.scripts.asc_to_qsch import convert_asc_to_qsch
        convert_asc_to_qsch(test_dir + "DC sweep.asc", temp_dir + "DC_sweep_from_asc.qsch")
        equalFiles(self, temp_dir + 'DC_sweep_from_asc.qsch', golden_dir + "DC_sweep_from_asc.qsch")

    # def test_qsch_to_asc(self):
    #     self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "DC sweep.qsch")
    #     self.edt.save_asc(temp_dir + "DC sweep.asc")
    #     equalFiles(self, temp_dir + 'DC sweep.asc', golden_dir + "DC sweep.asc")


class QschEditorFloatingNet(unittest.TestCase):

    def test_floating_net(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "Qspice_bug_floating_net.qsch")
        x1 = self.edt['X1']
        self.assertEqual(len(x1.ports), 3, "X1 should have only 3 pins connected")
        self.edt.save_netlist(temp_dir + 'qsch_floating_net.net')
        equalFiles(self, temp_dir + 'qsch_floating_net.net', golden_dir + "qsch_floating_net.net")


class QschEditorEmbeddedSubckt(unittest.TestCase):

    def test_embedded_subckt(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "Qspice_bug_embedded_subckt.qsch")
        self.edt.save_netlist(temp_dir + 'qsch_embedded_subckt.net')
        equalFiles(self, temp_dir + 'qsch_embedded_subckt.net', golden_dir + "qsch_embedded_subckt.net")

    def test_sub_circuit(self):
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "Qspice_top.qsch")
        # get sub-circuit
        sub = self.edt.get_subcircuit("X2")
        sub_desc = self.edt.get_component_value('X2')
        self.assertEqual("sub_circuit2", sub_desc, "Value mismatch")
        self.assertEqual('10K', sub.get_component_value("R1"))
        self.assertEqual('22K', sub.get_component_value("R4"))
        sub.set_component_value('R5', 220)
        self.edt.save_netlist(temp_dir + 'Qspice_top_edit.net')
        equalFiles(self, golden_dir + 'Qspice_top_edit.net', temp_dir + 'Qspice_top_edit.net')

    def test_bad_param(self):
        # This tests for a .param that is a comment. It should not be found therefore.
        self.edt = spicelib.editor.qsch_editor.QschEditor(test_dir + "Qspice_bad_param.qsch")
        try:
            self.edt.get_parameter("R")
            self.fail("Should have raised an exception")
        except Exception:
            pass        


if __name__ == '__main__':
    unittest.main()
