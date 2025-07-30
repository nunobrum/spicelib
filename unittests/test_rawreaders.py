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
from typing import Union

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../"))
)  # add project root to lib search path

import spicelib
from spicelib.raw.raw_read import RawRead
from numpy import pi, angle, exp

test_dir = "../examples/testfiles/" if os.path.abspath(os.curdir).endswith("unittests") else "./examples/testfiles/"
temp_dir = "./temp/" if os.path.abspath(os.curdir).endswith("unittests") else "./unittests/temp/"

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
# LTspice.exe -Run -b dc_rawtest.net
# cp dc_rawtest.raw dc_ltspice.bin.raw
# LTspice.exe -ascii -Run -b dc_rawtest.net
# cp dc_rawtest.raw dc_ltspice.ascii.raw
# # LTspice does not have sensitivity analysis, so we cannot test that

#
# ngspice -D ngbehavior=kiltspa -b -o ac_ngspice.log -r ac_ngspice.bin.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o ac_ngspice.log -r ac_ngspice.ascii.raw ac_rawtest.net
# ngspice -D ngbehavior=kiltspa -b -o tran_ngspice.log -r tran_ngspice.bin.raw tran_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o tran_ngspice.log -r tran_ngspice.ascii.raw tran_rawtest.net
# # I do not have the netlist for the noise files
# ngspice -D ngbehavior=kiltspa -b op_multi_ngspice_rawtest.net
# ngspice -D ngbehavior=kiltspa -b dc_ngspice_rawtest.net
# ngspice -D ngbehavior=kiltspa -b -o dc_ngspice.log -r dc2_ngspice.bin.raw dc_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o dc_ngspice.log -r dc2_ngspice.ascii.raw dc_rawtest.net
# ngspice -D ngbehavior=kiltspa -b -o sens_ngspice.log -r sens_ngspice.bin.raw sens_ngspice_rawtest.net
# ngspice -D ngbehavior=kiltspa -D filetype=ascii -b -o sens_ngspice.log -r sens_ngspice.ascii.raw sens_ngspice_rawtest.net

# xyce -r ac_xyce.bin.raw ac_rawtest.net
# xyce -r ac_xyce.ascii.raw -a ac_rawtest.net
# xyce -r tran_xyce.bin.raw tran_rawtest.net
# xyce -r tran_xyce.ascii.raw -a tran_rawtest.net
# xyce -r dc_xyce.bin.raw dc_rawtest.net
# xyce -r dc_xyce.ascii.raw -a dc_rawtest.net
# # and some files with nasty csv stuff following the data
# xyce -r sens_xyce.bin.raw sens_xyce_rawtest.net
# xyce -r sens_xyce.ascii.raw -a sens_xyce_rawtest.net

# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r ac_qspice.bin.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r ac_qspice.ascii.qraw -o ac_rawtest.log ac_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r tran_qspice.bin.qraw -o tran_rawtest.log tran_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r tran_qspice.ascii.qraw -o tran_rawtest.log tran_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -binary -r dc_qspice.bin.qraw -o dc_rawtest.log dc_rawtest.net
# c:\"Program Files"\QSPICE\QSPICE64.exe -ascii -r dc_qspice.ascii.qraw -o dc_rawtest.log dc_rawtest.net

# Stepped files are tested in test_spicelib and test_qspice_rawread.py

# generic values for the RC circuit used in AC and TRAN
R1 = 1000
C1 = 1e-6
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
        "dc": {
            "files": ["dc_ltspice.bin.raw", "dc_ltspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "DC transfer characteristic", 
                    "tracenames": ["V1", "V(r)", "I(V1)", "I(R1)"], 
                    "tracelen": 6
                },
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
                    "name": "Integrated Noise",
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
                    "values": [[1], [1e-3], [-1e-3]],
                },
                {
                    "name": "Operating Point",
                    "tracenames": ["v(vdd)", "i(@r1[i])", "i(v6)"],
                    "tracelen": 1,
                    "values": [[2], [2e-3], [-2e-3]],
                },
                {
                    "name": "Operating Point",
                    "tracenames": ["v(vdd)", "i(@r1[i])", "i(v6)"],
                    "tracelen": 1,
                    "values": [[3], [3e-3], [-3e-3]],
                },
            ],
        },
        "dc": {
            "files": ["dc_ngspice.bin.raw", "dc_ngspice.ascii.raw", "dc_c_ngspice.bin.raw", "dc_c_ngspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "DC transfer characteristic", 
                    "tracenames": ["v(v-sweep)", "v(r)", "i(v1)"], 
                    "tracelen": 6},
            ],
        },
        "sens": {
            "files": ["sens_ngspice.bin.raw", "sens_ngspice.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Sensitivity Analysis",
                    "tracenames": [
                        "frequency",
                        "v(m1:vto)",
                        "v(m1:kp)",
                        "v(m1:gamma)",
                        "v(m1:phi)",
                        "v(m1:lambda)",
                        "v(m1:rd)",
                        "v(m1:rs)",
                        "v(m1:cbd)",
                        "v(m1:cbs)",
                        "v(m1:is)",
                        "v(m1:pb)",
                        "v(m1:cgso)",
                        "v(m1:cgdo)",
                        "v(m1:cgbo)",
                        "v(m1:rsh)",
                        "v(m1:cj)",
                        "v(m1:mj)",
                        "v(m1:cjsw)",
                        "v(m1:mjsw)",
                        "v(m1:js)",
                        "v(m1:tox)",
                        "v(m1:ld)",
                        "v(m1:u0)",
                        "v(m1:fc)",
                        "v(m1:nsub)",
                        "v(m1:nss)",
                        "v(m1:tnom)",
                        "v(m1:kf)",
                        "v(m1:af)",
                        "v(m1:gdsnoi)",
                        "v(m1_m)",
                        "v(m1_l)",
                        "v(m1_w)",
                        "v(m1_ad)",
                        "v(m1_as)",
                        "v(m1_pd)",
                        "v(m1_ps)",
                        "v(m1_nrd)",
                        "v(m1_nrs)",
                        "v(m1_icvds)",
                        "v(m1_icvgs)",
                        "v(m1_icvbs)",
                        "v(m1_temp)",
                        "v(m1_dtemp)",
                        "v(r2:rsh)",
                        "v(r2:narrow)",
                        "v(r2:short)",
                        "v(r2:tc1)",
                        "v(r2:tc2)",
                        "v(r2:tce)",
                        "v(r2:kf)",
                        "v(r2:af)",
                        "v(r2:r)",
                        "v(r2:bv_max)",
                        "v(r2:lf)",
                        "v(r2:wf)",
                        "v(r2:ef)",
                        "v(r2)",
                        "v(r2_ac)",
                        "v(r2_temp)",
                        "v(r2_dtemp)",
                        "v(r2_l)",
                        "v(r2_w)",
                        "v(r2_m)",
                        "v(r2_tc)",
                        "v(r2_tc2)",
                        "v(r2_tce)",
                        "v(r2_bv_max)",
                        "v(r2_scale)",
                        "v(r1:rsh)",
                        "v(r1:narrow)",
                        "v(r1:short)",
                        "v(r1:tc1)",
                        "v(r1:tc2)",
                        "v(r1:tce)",
                        "v(r1:kf)",
                        "v(r1:af)",
                        "v(r1:r)",
                        "v(r1:bv_max)",
                        "v(r1:lf)",
                        "v(r1:wf)",
                        "v(r1:ef)",
                        "v(r1)",
                        "v(r1_ac)",
                        "v(r1_temp)",
                        "v(r1_dtemp)",
                        "v(r1_l)",
                        "v(r1_w)",
                        "v(r1_m)",
                        "v(r1_tc)",
                        "v(r1_tc2)",
                        "v(r1_tce)",
                        "v(r1_bv_max)",
                        "v(r1_scale)",
                        "v(v1)",
                        "v(v1_acmag)",
                        "v(v1_acphase)",
                        "v(v1_z0)",
                        "v(v1_pwr)",
                        "v(v1_freq)",
                        "v(v1_phase)",
                    ],
                    "tracelen": 31,
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
        "dc": {
            "files": ["dc_xyce.bin.raw", "dc_xyce.ascii.raw"],
            "expected_plots": [
                {"name": "DC transfer characteristic", "tracenames": ["sweep", "R", "V1#branch"], "tracelen": 6},
            ],
        },
        "sens": {
            "files": ["sens_xyce.bin.raw", "sens_xyce.ascii.raw"],
            "expected_plots": [
                {
                    "name": "Transient Analysis",
                    "tracenames": ["time", "V(1)", "V(2)", "V1#branch"],
                    "tracelen": 11,
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
        "dc": {
            "files": ["dc_qspice.bin.qraw", "dc_qspice.ascii.qraw"],
            "expected_plots": [
                {
                    "name": "DC Transfer Characteristic",
                    "tracenames": ["V1", "V(r)", "I(V1)", "P(R1)", "P(V1)", "I(R1)"],
                    "tracelen": 6,
                },
            ],
        },
    },
}


class RawReader_Test(unittest.TestCase):

    def _testframe(self, type: str, func):
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
                    raw = RawRead(f"{test_dir}{file}", dialect=dialect)
                    self.assertEqual(raw.dialect, simulator, "Difference in dialect")

                    nrplots = len(testset[simulator][type]["expected_plots"])
                    self.assertEqual(nrplots, raw.get_nr_plots(), "Number of plots does not match expected number")
                    for v in testset[simulator][type]["expected_plots"]:
                        expected_plotname = v["name"]
                        expected_tracenames = v["tracenames"]
                        expected_tracelen = v["tracelen"]
                        if "values" in v:
                            expected_values = v["values"]
                        else:
                            expected_values = None
                        if "has_axis" in v:
                            has_axis = v["has_axis"]
                        else:
                            has_axis = True

                        if not isinstance(expected_tracelen, int):
                            expected_tracelen = expected_tracelen[fileno - 1]
                        plotnr += 1

                        print(
                            f"Expected plot: '{expected_plotname}', tracenames: {expected_tracenames}, tracelen: {expected_tracelen}"
                        )

                        if nrplots == 1:
                            gotten_plotname = raw.get_plot_name()
                            gotten_tracenames = raw.get_trace_names()
                            gotten_flags = raw.get_raw_property("Flags")
                            my_raw = raw
                        else:
                            gotten_plotname = raw.plots[plotnr - 1].get_plot_name()
                            gotten_tracenames = raw.plots[plotnr - 1].get_trace_names()
                            gotten_flags = raw.plots[plotnr - 1].get_raw_property("Flags")
                            my_raw = raw.plots[plotnr - 1]
                        print(f"Gotten plot:   '{gotten_plotname}', tracenames: {gotten_tracenames}")

                        self.assertTrue(gotten_plotname is not None, "Plot name should not be None")
                        # the endswith stuff below is because of xyce: https://github.com/Xyce/Xyce/issues/157
                        self.assertTrue(
                            gotten_plotname.lower().endswith(expected_plotname.lower()), "Difference in plot name"
                        )
                        print(f"Flags: {gotten_flags}")

                        # Check if the expected tracenames are in the gotten tracenames, case insensitive
                        for expected_tracename in expected_tracenames:
                            self.assertIn(
                                expected_tracename.lower(),
                                (name.lower() for name in gotten_tracenames),
                                f"Expected trace name {expected_tracename} not found in {gotten_tracenames}",
                            )

                        main_axis = expected_tracenames[0].lower()
                        tracelen = len(my_raw.get_trace(main_axis).data)
                        print(f"tracelen, for {main_axis}: {tracelen}")
                        self.assertEqual(tracelen, expected_tracelen, "Not the expected number of points")
                        self.assertEqual(tracelen, my_raw.get_len(), "Not the expected number of points on the axis")

                        if expected_values is not None:
                            # Check the values of the traces, if we have them
                            for trace_name, expected_value in zip(expected_tracenames, expected_values):
                                trace = my_raw.get_trace(trace_name)
                                if isinstance(expected_value, list):
                                    # If we have a list, it is a multi-value trace
                                    for i, value in enumerate(expected_value):
                                        self.assertAlmostEqual(
                                            trace.data[i],
                                            value,
                                            msg=f"Data for {trace_name} at index {i} does not match expected value",
                                            delta=1e-6,
                                        )
                                else:
                                    # Otherwise it is a single value
                                    self.assertAlmostEqual(
                                        trace.data[0],
                                        expected_value,
                                        msg=f"Data for {trace_name} does not match expected value",
                                        delta=1e-6,
                                    )

                        if func is not None:
                            # Call the function passed as argument, to perform additional tests
                            func(my_raw, expected_tracelen, tracelen, main_axis if has_axis else None)

    def test_rawreaders_ac(self):
        # All AC tests use the same circuit as source, and the same simulation configuration
        # As a result, we can reuse the same expected values for all AC tests

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):

            expected_range = (1, 100000)

            # Check the range of the main axis, if we have it, and method depending on the type
            if main_axis is not None:
                gotten_range = (
                    round(abs(raw.get_trace(main_axis).data[0])),
                    round(abs(raw.get_trace(main_axis).data[tracelen - 1])),
                )
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
            for point, freq in enumerate(
                raw.get_axis()
            ):  # not .axis, since ltspice sometimes gives negative frequencies
                # print(f"testing pt {point} for freq {abs(freq)}")
                vout1 = vout_trace.get_point_at(freq)
                vout2 = vout_trace.get_point(point)
                vin = vin_trace.get_point(point)
                self.assertEqual(vout1, vout2, "Trace lookup problem")
                self.assertEqual(abs(vin), VIN, "Data problem on V(in)")
                # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
                h = vin / (1 + 2j * pi * freq * R1 * C1)
                self.assertAlmostEqual(
                    abs(vout1), abs(h), 5, f"Difference between theoretical value and simulation at point {point}"
                )
                self.assertAlmostEqual(
                    angle(vout1), angle(h), 5, f"Difference between theoretical value and simulation at point {point}"
                )

            # see if we can read alias traces as well
            test_name = "i(r1)"
            if test_name in (name.lower() for name in raw.get_trace_names()):
                tracelen = len(raw.get_trace(test_name).data)
                print(f"tracelen, for {test_name}: {tracelen}")
                self.assertEqual(
                    tracelen, expected_tracelen, f"Not the expected number of points for trace {test_name}"
                )

        self._testframe("ac", mytest)

    def test_rawreaders_tran(self):
        # All TRAN tests use the same circuit as source, and the same simulation configuration
        # As a result, we can reuse the same expected values for all TRAN tests

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):
            expected_range = (0, 5e-3)

            # Check the range of the main axis, if we have it, and method depending on the type
            if main_axis is not None:
                gotten_range = (
                    abs(raw.get_trace(main_axis).data[0]),
                    abs(raw.get_trace(main_axis).data[tracelen - 1]),
                )
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
                self.assertAlmostEqual(
                    abs(vout1), vout, 3, f"Difference between theoretical value and simulation at point {point}"
                )

            # see if we can read alias traces as well
            # Note that in the qspice ASCII file, there is a param with eng notation. That is on purpose, as caused a bug.
            test_name = "i(r1)"
            if test_name in (name.lower() for name in raw.get_trace_names()):
                tracelen = len(raw.get_trace(test_name).data)
                print(f"tracelen, for {test_name}: {tracelen}")
                self.assertEqual(
                    tracelen, expected_tracelen, f"Not the expected number of points for trace {test_name}"
                )

        self._testframe("tran", mytest)

    def test_rawreaders_noise(self):

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):
            expected_range = (1000, 10000000)

            # Check the range of the main axis, if we have it, and method depending on the type
            if main_axis is not None:
                # Round the first and last values to the nearest integer
                gotten_range = (
                    round(abs(raw.get_trace(main_axis).data[0])),
                    round(abs(raw.get_trace(main_axis).data[tracelen - 1])),
                )
                self.assertEqual(gotten_range, expected_range, f"{main_axis} range is not as expected")

        self._testframe("noise", mytest)

    def test_rawreaders_op(self):

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):
            pass

        self._testframe("op", mytest)

    def test_rawreaders_dc(self):
        # All DC tests use the same circuit as source, and the same simulation configuration
        # As a result, we can reuse the same expected values for all DC tests
        # ngspice generation is different: I have a set from a control section, and a set from the regular input
        # The results are comparable

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):
            expected_range = (0, 5)

            if main_axis is not None:
                # Round the first and last values to the nearest integer
                gotten_range = (
                    round(abs(raw.get_trace(main_axis).data[0])),
                    round(abs(raw.get_trace(main_axis).data[tracelen - 1])),
                )
                self.assertEqual(gotten_range, expected_range, f"{main_axis} range is not as expected")

            # Now DC specific tests
            v_name = "v(r)"
            if v_name not in (name.lower() for name in raw.get_trace_names()):
                v_name = "R"
            i_name = "i(v1)"
            if i_name not in (name.lower() for name in raw.get_trace_names()):
                i_name = "V1#branch"
            v_trace = raw.get_trace(v_name)
            i_trace = raw.get_trace(i_name)
            nr = -1
            for point, v_in in enumerate(raw.get_axis()):  # not .axis, since ltspice sometimes gives negative times
                nr += 1
                vt = v_trace.get_point_at(v_in)
                v = v_trace.get_point(point)
                i = i_trace.get_point(point)
                # print(f"Testing point {point} for v_in {v_in}: vt={vt}, v={v}, i={i}")
                self.assertEqual(vt, v, "Trace lookup problem")
                self.assertAlmostEqual(
                    v, i * -1000, 3, f"Difference between theoretical value and simulation at point {point}"
                )

        self._testframe("dc", mytest)

    def test_rawreaders_sens(self):

        def mytest(raw, expected_tracelen: int, tracelen: int, main_axis: Union[str, None] = None):
            pass

        self._testframe("sens", mytest)
        
        
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting tests on rawreaders")
    unittest.main(failfast=True)
    print("Tests completed on rawreaders")
# ------------------------------------------------------------------------------
