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
@email:         nuno.brum@gmail.com

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

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path

import spicelib
from spicelib.raw.raw_read import RawRead
from numpy import pi, angle, exp

test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
temp_dir = './temp/' if os.path.abspath(os.curdir).endswith('unittests') else './unittests/temp/'

if not os.path.exists(temp_dir):
    os.mkdir(temp_dir)

loglevel = logging.INFO
# set the logger to print to console and at desired level
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=loglevel)
spicelib.set_log_level(loglevel)

# commands used to generate the raw files:
#
# LTspice.exe -Run -b ac_rawtest.net
# cp ac_rawtest.raw ac_ltspice.bin.raw
# LTspice.exe -ascii -Run -b ac_rawtest.net
# cp ac_rawtest.raw ac_ltspice.ascii.raw
# LTspice.exe -Run -b tran_rawtest.net
# cp tran_rawtest.raw tran_ltspice.bin.raw
# LTspice.exe -ascii -Run -b tran_rawtest.net
# cp tran_rawtest.raw tran_ltspice.ascii.raw
# cp tran_ltspice.bin.raw tran_ltspice.fast.bin.raw
# LTspice.exe -fastaccess tran_ltspice.fast.bin.raw
#
# ngspice -D ngbehavior=kiltspa -b -o ac_ngspice.log -r ac_ngspice.bin.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o ac_ngspice.log -r ac_ngspice.ascii.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -b -o tran_ngspice.log -r tran_ngspice.bin.raw tran_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o tran_ngspice.log -r tran_ngspice.ascii.raw tran_rawtest.net
# ngspice -D ngbehavior=kiltspa -b multi_rawtest.net

# xyce -r ac_xyce.bin.raw ac_rawtest.net
# xyce -r ac_xyce.ascii.raw -a ac_rawtest.net
# xyce -r tran_xyce.bin.raw tran_rawtest.net
# xyce -r tran_xyce.ascii.raw -a tran_rawtest.net

# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r ac_qspice.bin.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r ac_qspice.ascii.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r tran_qspice.bin.qraw -o tran_rawtest.log tran_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r tran_qspice.ascii.qraw -o tran_rawtest.log tran_rawtest.net

# Stepped files are tested in test_spicelib and test_qspice_rawread.py


expected_ac_range = (1, 100000)
expected_tran_range = (0, 5e-3)
expected_noise_range = (1000, 10000000)
R1 = 1000
C1 = 1E-6
VIN = 1
testset = {
    "ltspice": {
        "ac": {
            "files": ["ac_ltspice.bin.raw", "ac_ltspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "AC Analysis",
                    "tracenames": ["frequency", "V(out)", "V(in)", "I(Vin)", "I(C1)", "I(R1)"],
                    "tracelen": 51,
                }
            ],
        },
        "tran": {
            "files": ["tran_ltspice.bin.raw", "tran_ltspice.ascii.raw", "tran_ltspice.fast.bin.raw"],
            "expected_plots": [
                {
                    "name": "Transient Analysis",
                    "tracenames": ["time", "V(out)", "V(in)", "I(Vin)", "I(C1)", "I(R1)"],
                    "tracelen": [21, 1049, 21],
                }
            ],
        },
    },
    "ngspice": {
        "ac": {
            "files": ["ac_ngspice.bin.raw", "ac_ngspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "AC Analysis",
                    "tracenames": ["frequency", "v(in)", "v(out)", "i(vin)"],
                    "tracelen": 51,
                },
            ],
        },
        "tran": {
            "files": ["tran_ngspice.bin.raw", "tran_ngspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Transient Analysis",
                    "tracenames": ["time", "v(in)", "v(out)", "i(vin)"],
                    "tracelen": 500013,
                },
            ],
        },
        "noise": {
            "files": ["noise_multi.bin.raw", "noise_multi.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Noise Spectral Density Curves",
                    "tracenames": ["frequency", "inoise_spectrum", "onoise_spectrum"],
                    "tracelen": 401,
                },
                {
                    "name":"Integrated Noise",
                    "tracenames": ["v(onoise_total)", "i(inoise_total)"],
                    "tracelen": 1,
                    "has_axis": False,  # No axis for this plot, True by default
                },
            ],
        },
        "op": {
            "files": ["op_multi_ngspice.bin.raw", "op_multi_ngspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Operating Point",
                    "tracenames": ["v(vdd)", "i(@r1[i])", "i(v6)"],
                    "tracelen": 1,
                },
                {
                    "name": "Operating Point",
                    "tracenames": ["v(vdd)", "i(@r1[i])", "i(v6)"],
                    "tracelen": 1,
                },
                {
                    "name": "Operating Point",
                    "tracenames": ["v(vdd)", "i(@r1[i])", "i(v6)"],
                    "tracelen": 1,
                },
            ],
        },
    },
    "xyce": {
        "ac": {
            "files": ["ac_xyce.bin.raw", "ac_xyce.ascii.raw"],
            "expected_plots": [
                {
                    "name": "AC Analysis",
                    "tracenames": ["frequency", "IN", "OUT", "VIN#branch"],
                    "tracelen": 51,
                },
            ],
        },
        "tran": {
            "files": ["tran_xyce.bin.raw", "tran_xyce.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Transient Analysis",
                    "tracenames": ["time", "IN", "OUT", "VIN#branch"],
                    "tracelen": 63,
                },
            ],
        },
        "force_dialect": True,
    },
    "qspice": {
        "ac": {
            "files": ["ac_qspice.bin.qraw", "ac_qspice.ascii.qraw"],
            "expected_plots": [
                {
                    "name": "AC Analysis",
                    "tracenames": [
                        "Frequency",
                        "V(in)",
                        "V(out)",
                        "I(VIN)",
                        "I(C1)",
                        "I(R1)",
                        "Freq",
                        "Omega",
                    ],
                    "tracelen": 50,
                },
            ],
        },
        "tran": {
            "files": ["tran_qspice.bin.qraw", "tran_qspice.ascii.qraw"],
            "expected_plots": [
                {
                    "name": "Transient Analysis",
                    "tracenames": ["Time", "V(in)", "V(out)", "I(VIN)", "I(C1)", "I(R1)"],
                    "tracelen": 1034,
                },
            ],
        },
    },
}


class RawReader_Test(unittest.TestCase):
    
    def test_rawreaders_ac(self):
        type = "ac"
        expected_range = expected_ac_range
        
        # BEGIN standard section
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator 

            if type in testset[simulator]:
                fileno = 0
                for file in testset[simulator][type]["files"]:
                    print(f"Testing {simulator} with file {file}")
                    plotnr = 0
                    fileno += 1
                    nrplots = len(testset[simulator][type]["expected_plots"])
                    for v in testset[simulator][type]["expected_plots"]:
                        expected_plotname = v['name']
                        expected_tracenames = v['tracenames']
                        expected_tracelen = v['tracelen']
                        if "has_axis" in v:
                            has_axis = v["has_axis"]
                        else:
                            has_axis = True
                            
                        if not isinstance(expected_tracelen, int):
                            expected_tracelen = expected_tracelen[fileno - 1]
                        print(f"Expected plot: {expected_plotname}, tracenames: {expected_tracenames}, tracelen: {expected_tracelen}")
                        plotnr += 1
                        
                        raw = RawRead(f"{test_dir}{file}", dialect=dialect, plot_to_read=plotnr)
                        self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                        self.assertEqual(raw.get_plot_name(), expected_plotname, "Difference in plot name")
                        for p in ["Flags"]:
                            print(f"{p}: {raw.get_raw_property(p)}")
                        if plotnr == nrplots:
                            self.assertEqual(raw.has_more_plots(), False, "There should be no more plots")

                        print(f"tracenames: {raw.get_trace_names()}")
                        self.assertEqual(raw.get_trace_names(), expected_tracenames, "Difference in trace names")
                        main_axis = expected_tracenames[0].lower()
                        tracelen = len(raw.get_trace(main_axis).data)
                        print(f"tracelen, for {main_axis}: {tracelen}")
                        self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                        self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")                         
                        # END standard section
                        
                        # Check the range of the main axis, if we have it, and method depending on the type
                        if has_axis:
                            gotten_range = (round(abs(raw.get_trace(main_axis).data[0])), round(abs(raw.get_trace(main_axis).data[tracelen - 1])))                
                            self.assertEqual(gotten_range, expected_range, f"{main_axis} range is not as expected")
                        
                        # Now Frequency specific tests
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

                        # see if we can read alias traces as well
                        test_name = "i(r1)"
                        if test_name in (name.lower() for name in raw.get_trace_names()):
                            tracelen = len(raw.get_trace(test_name).data)
                            print(f"tracelen, for {test_name}: {tracelen}")
                            self.assertEqual(tracelen, expected_tracelen, f"Not the expected number of points for trace {test_name}")

    def test_rawreaders_tran(self):
        type = "tran"
        expected_range = expected_tran_range

        # BEGIN standard section
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator 

            if type in testset[simulator]:
                fileno = 0
                for file in testset[simulator][type]["files"]:
                    print(f"Testing {simulator} with file {file}")
                    plotnr = 0
                    fileno += 1
                    nrplots = len(testset[simulator][type]["expected_plots"])
                    for v in testset[simulator][type]["expected_plots"]:
                        expected_plotname = v['name']
                        expected_tracenames = v['tracenames']
                        expected_tracelen = v['tracelen']
                        if "has_axis" in v:
                            has_axis = v["has_axis"]
                        else:
                            has_axis = True
                            
                        if not isinstance(expected_tracelen, int):
                            expected_tracelen = expected_tracelen[fileno - 1]
                        print(f"Expected plot: {expected_plotname}, tracenames: {expected_tracenames}, tracelen: {expected_tracelen}")
                        plotnr += 1
                        
                        raw = RawRead(f"{test_dir}{file}", dialect=dialect, plot_to_read=plotnr)
                        self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                        self.assertEqual(raw.get_plot_name(), expected_plotname, "Difference in plot name")
                        for p in ["Flags"]:
                            print(f"{p}: {raw.get_raw_property(p)}")
                        if plotnr == nrplots:
                            self.assertEqual(raw.has_more_plots(), False, "There should be no more plots")

                        print(f"tracenames: {raw.get_trace_names()}")
                        self.assertEqual(raw.get_trace_names(), expected_tracenames, "Difference in trace names")
                        main_axis = expected_tracenames[0].lower()
                        tracelen = len(raw.get_trace(main_axis).data)
                        print(f"tracelen, for {main_axis}: {tracelen}")
                        self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                        self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")                         
                        # END standard section
                        
                        # Check the range of the main axis, if we have it, and method depending on the type
                        if has_axis:
                            gotten_range = (abs(raw.get_trace(main_axis).data[0]), abs(raw.get_trace(main_axis).data[tracelen - 1]))
                            self.assertEqual(gotten_range, expected_range, f"{main_axis} range is not as expected")

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

                        # see if we can read alias traces as well
                        # Note that in the qspice ASCII file, there is a param with eng notation. That is on purpose, as caused a bug.
                        test_name = "i(r1)"
                        if test_name in (name.lower() for name in raw.get_trace_names()):
                            tracelen = len(raw.get_trace(test_name).data)
                            print(f"tracelen, for {test_name}: {tracelen}")
                            self.assertEqual(tracelen, expected_tracelen, f"Not the expected number of points for trace {test_name}")

    def test_rawreaders_noise(self):
        type = "noise"
        expected_range = expected_noise_range
        
        # BEGIN standard section
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator 

            if type in testset[simulator]:
                fileno = 0
                for file in testset[simulator][type]["files"]:
                    print(f"Testing {simulator} with file {file}")
                    plotnr = 0
                    fileno += 1
                    nrplots = len(testset[simulator][type]["expected_plots"])
                    for v in testset[simulator][type]["expected_plots"]:
                        expected_plotname = v['name']
                        expected_tracenames = v['tracenames']
                        expected_tracelen = v['tracelen']
                        if "has_axis" in v:
                            has_axis = v["has_axis"]
                        else:
                            has_axis = True
                            
                        if not isinstance(expected_tracelen, int):
                            expected_tracelen = expected_tracelen[fileno - 1]
                        print(f"Expected plot: {expected_plotname}, tracenames: {expected_tracenames}, tracelen: {expected_tracelen}")
                        plotnr += 1
                        
                        raw = RawRead(f"{test_dir}{file}", dialect=dialect, plot_to_read=plotnr)
                        self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                        self.assertEqual(raw.get_plot_name(), expected_plotname, "Difference in plot name")
                        for p in ["Flags"]:
                            print(f"{p}: {raw.get_raw_property(p)}")
                        if plotnr == nrplots:
                            self.assertEqual(raw.has_more_plots(), False, "There should be no more plots")

                        print(f"tracenames: {raw.get_trace_names()}")
                        self.assertEqual(raw.get_trace_names(), expected_tracenames, "Difference in trace names")
                        main_axis = expected_tracenames[0].lower()
                        tracelen = len(raw.get_trace(main_axis).data)
                        print(f"tracelen, for {main_axis}: {tracelen}")
                        self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                        self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")                         
                        # END standard section
                        
                        # Check the range of the main axis, if we have it, and method depending on the type
                        if has_axis:
                            # Round the first and last values to the nearest integer
                            gotten_range = (round(abs(raw.get_trace(main_axis).data[0])), round(abs(raw.get_trace(main_axis).data[tracelen - 1])))                
                            self.assertEqual(gotten_range, expected_range, f"{main_axis} range is not as expected")

    def test_rawreaders_op(self):
        type = "op"
        
        # BEGIN standard section
        for simulator in testset:
            dialect = None
            if "force_dialect" in testset[simulator] and testset[simulator]["force_dialect"]:
                dialect = simulator 

            if type in testset[simulator]:
                fileno = 0
                for file in testset[simulator][type]["files"]:
                    print(f"Testing {simulator} with file {file}")
                    plotnr = 0
                    fileno += 1
                    nrplots = len(testset[simulator][type]["expected_plots"])
                    for v in testset[simulator][type]["expected_plots"]:
                        expected_plotname = v['name']
                        expected_tracenames = v['tracenames']
                        expected_tracelen = v['tracelen']
                        if "has_axis" in v:
                            has_axis = v["has_axis"]
                        else:
                            has_axis = True
                            
                        if not isinstance(expected_tracelen, int):
                            expected_tracelen = expected_tracelen[fileno - 1]
                        print(f"Expected plot: {expected_plotname}, tracenames: {expected_tracenames}, tracelen: {expected_tracelen}")
                        plotnr += 1
                        
                        raw = RawRead(f"{test_dir}{file}", dialect=dialect, plot_to_read=plotnr)
                        self.assertEqual(raw.dialect, simulator, "Difference in dialect")
                        self.assertEqual(raw.get_plot_name(), expected_plotname, "Difference in plot name")
                        for p in ["Flags"]:
                            print(f"{p}: {raw.get_raw_property(p)}")
                        if plotnr == nrplots:
                            self.assertEqual(raw.has_more_plots(), False, "There should be no more plots")

                        print(f"tracenames: {raw.get_trace_names()}")
                        self.assertEqual(raw.get_trace_names(), expected_tracenames, "Difference in trace names")
                        main_axis = expected_tracenames[0].lower()
                        tracelen = len(raw.get_trace(main_axis).data)
                        print(f"tracelen, for {main_axis}: {tracelen}")
                        self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                        self.assertEqual(tracelen, len(raw.axis), "Not the expected number of points on the axis")                         
                        # END standard section
                        

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("Starting tests on rawreaders")
    unittest.main()
    print("Tests completed on rawreaders")
# ------------------------------------------------------------------------------
