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
# Name:        test_rawreaders.py
# Purpose:     Test the raw readers, in all dialects
#
# Author:      hb020
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
@author:        nunobrum
@copyright:     Copyright 2025

@license:       GPLv3
@maintainer:    Nuno Brum
@email:         nuno.brum@gmail.com

@file:          test_raw_write.py
@date:          2025-02-12

@note           spicelib raw_read unit test, on all supported simulators
                  run ./test/unittests/test_rawreaders
"""
import os  # platform independent paths
# ------------------------------------------------------------------------------
# Python Libs
import sys  # python path handling
import unittest  # performs test
import logging

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path


from spicelib import RawWrite, Trace
from spicelib import RawRead
import numpy as np


testfiles_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'


def has_ltspice_detect():
    from spicelib.simulators.ltspice_simulator import LTspice
    global ltspice_simulator
    ltspice_simulator = LTspice
    # return False
    return ltspice_simulator.is_available()


# ------------------------------------------------------------------------------
has_ltspice = has_ltspice_detect()
skip_ltspice_tests = not has_ltspice
print("skip_ltspice_tests", skip_ltspice_tests)
hide_exe_print_statements = True  # set to False if you want Spice to log to console
# ------------------------------------------------------------------------------


class TestRawWrite(unittest.TestCase):

    def equal_raw_files(self, file1, file2):
        raw1 = RawRead(file1)
        raw2 = RawRead(file2)
        # Test that it has the same information on header except for date and filename
        for param in raw1.get_raw_properties():
            if param in ["Date", "Filename", "No. Variables", "No. Points"]:
                continue
            if (param not in raw1.raw_params) and (param not in raw2.raw_params):
                continue
            self.assertEqual(raw1.raw_params[param], raw2.raw_params[param],f"Parameter {param} is the same")

        self.assertEqual(raw1.nVariables, raw2.nVariables, "Number of variables is the same")
        # Due to different configurations, the amount of points might slightly differ,
        # assert that we are within 1% tolerance
        self.assertAlmostEqual(raw1.nPoints, raw2.nPoints, delta=(raw1.nPoints / 100), msg="Number of points is the same")

        # Compare Vectors
        for trace_name in raw1.get_trace_names():
            trace1 = raw1.get_trace(trace_name)
            trace2 = raw2.get_trace(trace_name)
            self.assertEqual(trace1.numerical_type, trace2.numerical_type, "Traces of the same numerical type")
            # self.assertEqual(trace1.what_type, trace2.what_type, "Traces of the same kind")
            # self.assertListEqual(trace1.data, trace2.data, "Traces are the same")

    def test_tran_file(self):
        LW = RawWrite(fastacces=False)
        tx = Trace('time', np.arange(0.0, 3e-3, 997E-11))
        vy = Trace('N001', np.sin(2 * np.pi * tx.data * 10000))
        vz = Trace('N002', np.cos(2 * np.pi * tx.data * 9970))
        LW.add_trace(tx)
        LW.add_trace(vy)
        LW.add_trace(vz)
        LW.save(temp_dir + "two_freqs.raw")
        self.equal_raw_files(golden_dir + "two_freqs.raw", temp_dir + "two_freqs.raw")

    def test_axis_sync(self):  # Test axis sync
        LW = RawWrite()
        tx = Trace('time', np.arange(0.0, 3e-3, 997E-11))
        vy = Trace('N001', np.sin(2 * np.pi * tx.data * 10000))
        vz = Trace('N002', np.cos(2 * np.pi * tx.data * 9970))
        LW.add_trace(tx)
        LW.add_trace(vy)
        LW.add_trace(vz)
        LR = RawRead(testfiles_dir + "testfile.raw")
        LW.add_traces_from_raw(LR, ('V(out)',), force_axis_alignment=True)
        LW.save(temp_dir + "merge.raw")
        self.equal_raw_files(golden_dir + "merge.raw", temp_dir + "merge.raw")
        test = """
        equal = True
        for ii in range(len(tx)):
            if t[ii] != tx[ii]:
                print(t[ii], tx[ii])
                equal = False
        print(equal)

        v = LR.get_trace('N001')
        max_error = 1.5e-12
        for ii in range(len(vy)):
            err = abs(v[ii] - vy[ii])
            if err > max_error:
                max_error = err
                print(v[ii], vy[ii], v[ii] - vy[ii])
        print(max_error)
        """

    def test_write_ac(self):
        LW = RawWrite()
        LR = RawRead(testfiles_dir + "PI_Filter.raw")
        LR1 = RawRead(testfiles_dir + "PI_Filter_resampled.raw")
        LW.add_traces_from_raw(LR, ('V(N002)',))
        LW.add_traces_from_raw(LR1, 'V(N002)', rename_format='N002_resampled', force_axis_alignment=True)
        LW.flag_fastaccess = False
        LW.save(temp_dir + "PI_filter_rewritten.raw")
        self.equal_raw_files(golden_dir + "PI_filter_rewritten.raw", temp_dir + "PI_filter_rewritten.raw")
        LW.flag_fastaccess = True
        LW.save(temp_dir + "PI_filter_rewritten_fast.raw")
        self.equal_raw_files(golden_dir + "PI_filter_rewritten_fast.raw", temp_dir + "PI_filter_rewritten_fast.raw")

    def test_write_tran(self):
        LR = RawRead(testfiles_dir + "TRAN - STEP.raw")
        LW = RawWrite()
        LW.add_traces_from_raw(LR, ('V(out)', 'I(C1)'))
        LW.flag_fastaccess = False
        LW.save(temp_dir + "TRAN - STEP0_normal.raw")
        self.equal_raw_files(golden_dir + "TRAN - STEP0_normal.raw", temp_dir + "TRAN - STEP0_normal.raw")
        LW.flag_fastaccess = True
        LW.save(temp_dir + "TRAN - STEP0_fast.raw")
        self.equal_raw_files(golden_dir + "TRAN - STEP0_fast.raw", temp_dir + "TRAN - STEP0_fast.raw")

    def test_combine_tran(self):

        LW = RawWrite()
        for tag, raw in (
                ("AD820_15", testfiles_dir + "Batch_Test_AD820_15.raw"),
                # ("AD820_10", testfiles_dir + "Batch_Test_AD820_10.raw"),
                ("AD712_15", testfiles_dir + "Batch_Test_AD712_15.raw"),
                # ("AD712_10", testfiles_dir + "Batch_Test_AD712_10.raw"),
                # ("AD820_5", testfiles_dir + "Batch_Test_AD820_5.raw"),
                # ("AD712_5", testfiles_dir + "Batch_Test_AD712_5.raw"),
        ):
            LR = RawRead(raw)
            LW.add_traces_from_raw(LR, ("V(out)", "I(R1)"), add_tag=tag, force_axis_alignment=True)
        LW.flag_fastaccess = False
        LW.save(temp_dir + "Batch_Test_Combine.raw")
        self.equal_raw_files(golden_dir + "Batch_Test_Combine.raw", temp_dir + "Batch_Test_Combine.raw")

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_task_iterators(self):
        """
        @note   inits class
        """
        print("Starting test_batch_test")
        from spicelib.simulators.ltspice_simulator import LTspice
        from spicelib import SpiceEditor, SimRunner
        # prepare
        editor = SpiceEditor(testfiles_dir + "Batch_Test.net")
        runner = SimRunner(parallel_sims=4, output_folder="./output", simulator=LTspice)
        editor.set_parameters(res=0, cap=100e-6)
        for r2_value in ('1k', '2k', '4k'):
            editor.set_component_value('R2', r2_value)  # Modifying the value of a resistor
            runner.run(editor)

        for task in runner.tasks():
            self.assertTrue(hasattr(task, 'edits'), "edits dictionary exist on the task")
            self.assertEqual(3, len(task.edits), "All three edits were done")
            self.assertEqual('res', task.edits[0].name, "Updated res")
            self.assertEqual(0, task.edits[0].value, "Updated res")
            self.assertEqual('cap', task.edits[1].name, "Updated cap")
            self.assertEqual(100e-6, task.edits[1].value, "Updated cap")
            self.assertEqual('R2', task.edits[2].name, "Updated R2")
            self.assertEqual(0, task.edits['res'].value, "Access by name is working")
            self.assertEqual(0.0001, task.edits['cap'].value, "Access by name is working")
            self.assertIn(task.edits['R2'].value, ('1k', '2k', '4k'), "Access by name is working")

        count = 0
        for task in runner.tasks({'R2': ['1k', '4k']}):
            self.assertEqual(3, len(task.edits), "All three edits were done")
            self.assertEqual('R2', task.edits[2].name, "Updated R2")
            self.assertIn(task.edits['R2'].value, {'1k', '4k'}, "Access by name is working")
            count += 1
        self.assertEqual(2, count, "One task was retrieved")

        filter_func = lambda x: x.edits[2].value == '4k'
        count = 0
        for task in runner.tasks(filter_func):
            self.assertEqual('R2', task.edits[2].name, "Updated R2")
            self.assertEqual('4k', task.edits[2].value, "Updated R2")
            count += 1
        self.assertEqual(1, count, "One task was retrieved")

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_create_raw_file_with_filter(self):
        """
        @note   inits class
        """
        print("Starting test_batch_test")
        from spicelib.simulators.ltspice_simulator import LTspice
        from spicelib import SpiceEditor, SimRunner
        # prepare
        editor = SpiceEditor(testfiles_dir + "Batch_Test.net")
        runner = SimRunner(parallel_sims=4, output_folder="./output", simulator=LTspice)
        editor.set_parameters(res=0, cap=100e-6)
        for r2_value in ('1k', '5k', '10k'):
            editor.set_component_value('R2', r2_value)  # Modifying the value of a resistor
            runner.run(editor)

        runner.create_raw_file_with(temp_dir + "raw_created_from_runner.raw", ("V(out)", "I(R1)"),
                                    {'R2': ('5k', '10k')})
        self.equal_raw_files(golden_dir + "raw_created_from_runner.raw", temp_dir + "raw_created_from_runner.raw")


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting tests on raw_write")
    unittest.main(failfast=True)
    print("Tests completed on raw_write")
# ------------------------------------------------------------------------------
