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

@file:          test_raw_writer.py
@date:          2025-02-12

@note           spicelib raw_read unit test, on all supported simulators
                  run ./test/unittests/test_rawreaders
"""
import unittest
import os
from spicelib import RawWrite, Trace
from spicelib import RawRead
import numpy as np


testfiles_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'


class RawWriterTest(unittest.TestCase):

    def equal_raw_files(self, file1, file2):
        raw1 = RawRead(file1)
        raw2 = RawRead(file2)
        # Test that it has the same information on header except for date.
        for param in raw1.header_lines:
            if param == "Date":
                continue
            if (param not in raw1.raw_params) and (param not in raw2.raw_params):
                continue
            self.assertEqual(raw1.raw_params[param], raw2.raw_params[param],f"Parameter {param} is the same")

        self.assertEqual(raw1.nVariables, raw2.nVariables, "Number of variables is the same")
        self.assertEqual(raw1.nPoints, raw2.nPoints, "Number of points is the same")

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

