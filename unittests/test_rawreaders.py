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
@author:        hb020
@copyright:     Copyright 2025
@credits:       nunobrum

@license:       GPLv3
@maintainer:    Nuno Brum
@email:         me@nunobrum.com

@file:          test_rawreaders.py
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

import spicelib
from spicelib.raw.raw_read import RawRead
from numpy import pi, angle, exp

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
golden_dir = './golden/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/golden/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)


# set the logger to print to console and at info level
spicelib.set_log_level(logging.INFO)

# commands used to generate the raw files:
#
# (TODO: add ltspice commands)
#
# ngspice -D ngbehavior=kiltspa -b -o ac_ngspice.log -r ac_ngspice.bin.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o ac_ngspice.log -r ac_ngspice.ascii.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -b -o tran_ngspice.log -r tran_ngspice.bin.raw tran_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o tran_ngspice.log -r tran_ngspice.ascii.raw tran_rawtest.net

# xyce -r ac_xyce.bin.raw ac_rawtest.net
# xyce -r ac_xyce.ascii.raw -a ac_rawtest.net
# xyce -r tran_xyce.bin.raw tran_rawtest.net
# xyce -r tran_xyce.ascii.raw -a tran_rawtest.net

# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r ac_qspice.bin.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r ac_qspice.ascii.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r tran_qspice.bin.qraw -o tran_rawtest.log tran_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r tran_qspice.ascii.qraw -o tran_rawtest.log tran_rawtest.net

expected_ac_range = (1, 100000)
expected_time_range = (0, 5e-3)
R1 = 1000
C1 = 1E-6
VIN = 1
testset = {
    "ltspice": {
        "ac": {
            "files": ["ac_ltspice.bin.raw", "ac_ltspice.ascii.raw"],
            "expected_tracenames": ["frequency", "V(out)", "V(in)", "I(Vin)", "I(C1)", "I(R1)"],
            "expected_tracelen": 51
        },
        "tran": {
            "files": ["tran_ltspice.bin.raw", "tran_ltspice.ascii.raw"],
            "expected_tracenames": ["time", "V(out)", "V(in)", "I(Vin)", "I(C1)", "I(R1)"],
            "expected_tracelen": [23, 1049]
        },        
    },
    "ngspice": {
        "ac": {
            "files": ["ac_ngspice.bin.raw", "ac_ngspice.ascii.raw"],
            "expected_tracenames": ["frequency", "v(in)", "v(out)", "i(vin)"],
            "expected_tracelen": 51
        },
        "tran": {
            "files": ["tran_ngspice.bin.raw", "tran_ngspice.ascii.raw"],
            "expected_tracenames": ["time", "v(in)", "v(out)", "i(vin)"],
            "expected_tracelen": 500013
        },
    },
    "xyce": {
        "ac": {
            "files": ["ac_xyce.bin.raw", "ac_xyce.ascii.raw"],
            "expected_tracenames": ["frequency", "IN", "OUT", "VIN#branch"],
            "expected_tracelen": 51
        },
        "tran": {
            "files": ["tran_xyce.bin.raw", "tran_xyce.ascii.raw"],
            "expected_tracenames": ["time", "IN", "OUT", "VIN#branch"],
            "expected_tracelen": 63
        },
        "force_dialect": True
    },
    "qspice": {
        "ac": {
            "files": ["ac_qspice.bin.qraw", "ac_qspice.ascii.qraw"],
            "expected_tracenames": [
                "Frequency",
                "V(in)",
                "V(out)",
                "I(VIN)",
                "I(C1)",
                "I(R1)",
                "Freq",
                "Omega",
            ],
            "expected_tracelen": 50
        },
        "tran": {
            "files": ["tran_qspice.bin.qraw", "tran_qspice.ascii.qraw"],
            "expected_tracenames": ["Time", "V(in)", "V(out)", "I(VIN)", "I(C1)", "I(R1)"],
            "expected_tracelen": 1034
        },
    },
}


class RawReader_Test(unittest.TestCase):

    def test_rawreaders_ac(self):
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator 

            for file in testset[simulator]["ac"]["files"]:
                print(f"Testing {simulator} with file {file}")                    
                raw = RawRead(f"{test_dir}{file}", dialect=dialect)
                self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                
                print(f"tracenames: {raw.get_trace_names()}")
                self.assertEqual(raw.get_trace_names(), testset[simulator]["ac"]["expected_tracenames"], "Difference in trace names")
                tracelen = len(raw.get_trace("frequency").data)
                print(f"tracelen: {tracelen}")
                self.assertEqual(tracelen, testset[simulator]["ac"]["expected_tracelen"], "Not the expected number of points")
                self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")
                freqrange = (int(abs(raw.get_trace("frequency").data[0])), int(abs(raw.get_trace("frequency").data[tracelen - 1])))                
                self.assertEqual(freqrange, expected_ac_range, "Frequency range is not as expected")
                
                # Compute the RC AC response with the resistor and capacitor values from the netlist.
                vout_name = "v(out)"
                vin_name = "v(in)"
                if vout_name not in (name.lower() for name in raw.get_trace_names()):
                    vout_name = "out"
                    vin_name = "in"
                vout_trace = raw.get_trace(vout_name)
                vin_trace = raw.get_trace(vin_name)
                for point, freq in enumerate(raw.axis):
                    # print(f"testing pt {point} for freq {abs(freq)}")
                    vout1 = vout_trace.get_point_at(freq)
                    vout2 = vout_trace.get_point(point)
                    vin = vin_trace.get_point(point)
                    self.assertEqual(vout1, vout2, "Trace lookup problem")
                    self.assertEqual(abs(vin), VIN, "Data problem on V(in)")
                    # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
                    h = vin / (1 + 2j * pi * freq * R1 * C1)
                    self.assertAlmostEqual(abs(vout1), abs(h), 5, f"Difference between theoretical value and simulation at point {point}")
                    self.assertAlmostEqual(angle(vout1), angle(h), 5, f"Difference between theoretical value and simulation at point {point}")

    def test_rawreaders_tran(self):
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator             
            fileno = 0
            for file in testset[simulator]["tran"]["files"]:
                print(f"Testing {simulator} with file {file}")
                raw = RawRead(f"{test_dir}{file}", dialect=dialect)
                self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                
                print(f"tracenames: {raw.get_trace_names()}")
                self.assertEqual(raw.get_trace_names(), testset[simulator]["tran"]["expected_tracenames"], "Difference in trace names")
                tracelen = len(raw.get_trace("time").data)
                print(f"tracelen: {tracelen}")
                expected_tracelen = testset[simulator]["tran"]["expected_tracelen"]
                if isinstance(expected_tracelen, int):
                    self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                else:
                    self.assertEqual(tracelen, expected_tracelen[fileno], "Not the expected number of points")
                    
                self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")
                timerange = (abs(raw.get_trace("time").data[0]), abs(raw.get_trace("time").data[tracelen - 1]))
                self.assertEqual(timerange, expected_time_range, "Time range is not as expected")

                # Compute the RC transient response with the resistor and capacitor values from the netlist.
                vout_name = "v(out)"
                vin_name = "v(in)"
                if vout_name not in (name.lower() for name in raw.get_trace_names()):
                    vout_name = "out"
                    vin_name = "in"
                vout_trace = raw.get_trace(vout_name)
                vin_trace = raw.get_trace(vin_name)
                skip_samples = int(tracelen / 100)  # do about 100 samples
                nr = -1
                for point, tm in enumerate(raw.get_axis()):  # not .axis, since ltspice sometimes gives negative times
                    nr += 1
                    # skip extra samples
                    if nr < skip_samples:
                        continue
                    # take this sample
                    nr = -1
                    vout1 = vout_trace.get_point_at(tm)
                    vout2 = vout_trace.get_point(point)
                    vin = vin_trace.get_point(point)
                    self.assertEqual(vout1, vout2, "Trace lookup problem")
                    if tm > 1e-6:
                        # rising flank of the input voltage, give it some time
                        self.assertEqual(abs(vin), VIN, "Data problem on V(in)")
                    
                    # Calculate the magnitude of the answer Vout = Vin * (1 - e^(-t/RC))
                    vout = vin * (1 - exp(-1 * tm / (R1 * C1))) 
                    # print(f"testing pt {point} for time {tm}: vin={vin}, vout_sim={vout1}, vout_th={vout}")
                    self.assertAlmostEqual(abs(vout1), vout, 3, f"Difference between theoretical value and simulation at point {point}")

                fileno += 1
                

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("Starting tests on rawreaders")
    unittest.main()
    print("Tests completed on rawreaders")
# ------------------------------------------------------------------------------
