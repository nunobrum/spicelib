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
# import logging

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

    def test_subcircuits_edit(self):
        """Test subcircuits editing in the Asc Editor.
        The input is based on a top circuit plus a subcircuit that is not in a library.
        It uses the exact same tests as in test_spice_editor.py:test_subcircuits_edit():
        
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
        sc = "X1"
        # load the file here, as this is somewhat tricky, and I don't want to block the other tests too early
        my_edt = spicelib.editor.asc_editor.AscEditor(test_dir + "top_circuit.asc")
        
        # START identical part with test_spice_editor.py:test_subcircuits_edit()
        self.assertEqual(my_edt.get_subcircuit(sc).get_components(), ['C1', 'C2', 'L1'], "Subcircuit component list")        
        
        self.assertEqual(my_edt.get_component_value(sc + ":L1"), "1µ", "Subcircuit Value for X1:L1, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "1µ", "Subcircuit Value for X1:L1, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 1e-6, msg="Subcircuit Value for X1:L1, float comparison")
        
        my_edt.set_component_value(sc + ":L1", 2e-6)  # set float value, on compound component name
        self.assertEqual(my_edt[sc + ":L1"].value_str, "2u", "Subcircuit Value_str for X1:L1, after 1st change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "2u", "Subcircuit Value for X1:L1, after 1st change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 2e-6, msg="Subcircuit Value for X1:L1, after 1st change, float comparison")
        
        my_edt[sc + ":L1"].value = "3µH"  # set string value via compound method
        self.assertEqual(my_edt[sc + ":L1"].value_str, "3µH", "Subcircuit Value_str for X1:L1, after 2nd change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "3µH", "Subcircuit Value for X1:L1, after 2nd change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 3e-6, msg="Subcircuit Value for X1:L1, after 2nd change, float comparison")
        
        # now change the value to 4uH, because I don't want to deal with the µ character in equalFiles(). 
        my_edt.get_subcircuit(sc)["L1"].value = "4uH"  # set string value via indirect method
        self.assertEqual(my_edt[sc + ":L1"].value_str, "4uH", "Subcircuit Value_str for X1:L1, after 3rd change, direct")
        self.assertEqual(my_edt.get_subcircuit(sc).get_component_value("L1"), "4uH", "Subcircuit Value for X1:L1, after 3rd change, indirect")
        self.assertAlmostEqual(my_edt[sc + ":L1"].value, 4e-6, msg="Subcircuit Value for X1:L1, after 3rd change, float comparison")
        
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
        # END identical part with test_spice_editor.py:test_subcircuits_edit()
        
        S = my_edt.get_subcircuit(sc)
        S.asc_file_path = temp_dir + "subcircuit_edit.asc"  # Only for test purposes
        my_edt.save_netlist(temp_dir + "top_circuit_edit.asc")
        self.equalFiles(temp_dir + "top_circuit_edit.asc", golden_dir + "top_circuit_edit.asc")
        self.equalFiles(temp_dir + "subcircuit_edit.asc", golden_dir + "subcircuit_edit.asc")
        
    def test_subcircuit_block_in_lib(self):
        """Test subcircuit editing in the Asc Editor, with the component in a BLOCK and library.
        """
        # load the file here, as this is somewhat tricky, and I don't want to block the other tests too early
        my_edt = spicelib.editor.asc_editor.AscEditor(test_dir + "testcomp1.asc")
        self.assertAlmostEqual(my_edt["U1:R1"].value, 320, msg="Subcircuit Value for U1:R1, float comparison")
        my_edt["R2"].value = 20
        self.assertAlmostEqual(my_edt["R2"].value, 20, msg="Subcircuit Value for R2, float comparison after edit")
        
    def test_subcircuit_cell_in_lib(self):
        """Test subcircuit editing in the Asc Editor, with the component in a CELL and library.
        """
        # load the file here, as this is somewhat tricky, and I don't want to block the other tests too early
        my_edt = spicelib.editor.asc_editor.AscEditor(test_dir + "testcomp2.asc")
        self.assertAlmostEqual(my_edt["U1:R1"].value, 320, msg="Subcircuit Value for U1:R1, float comparison")
        my_edt["R2"].value = 20
        self.assertAlmostEqual(my_edt["R2"].value, 20, msg="Value for R2, float comparison after edit")
        
        # The following test is not working as it should, because the value is not being saved in save_netlist()
        # It also doesn't log via the logger, but that is another issue.
        self.assertTrue(my_edt.get_subcircuit("U1").is_read_only(), "Subcircuit U1 should be readonly")
        try:
            my_edt["U1:R1"].value = 330
        except:
            pass
        self.assertAlmostEqual(my_edt["U1:R1"].value, 320, msg="Subcircuit Value for U1:R1, modification should have been rejected")
        
        # my_edt.save_netlist(temp_dir + "testcomp2_edit.asc")
        # A test of the saved file is not really useful, because the subcircuit value changes are not saved.
        
    def equalFiles(self, file1, file2):
        with open(file1, 'r') as f1:
            lines1 = f1.readlines()
        with open(file2, 'r') as f2:
            lines2 = f2.readlines()
        self.assertEqual(len(lines1), len(lines2), "Number of lines is different")
        for i, lines in enumerate(zip(lines1, lines2)):
            self.assertEqual(lines[0], lines[1], "Line %d" % i)


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)  # Set up the root logger first
    # spicelib.set_log_level(logging.DEBUG) 
    # unittest.main(argv=["", "ASC_Editor_Test.test_subcircuit_cell_in_lib"])
    unittest.main()
