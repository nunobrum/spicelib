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
# Name:        test_qspice_rawread.py
# Purpose:     Unit testing for RawRead class using Qspice simulation resutls
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
@author:        Nuno Brum
@copyright:     Copyright 2022
@credits:       nunobrum

@license:       GPLv3
@maintainer:    Nuno Brum
@email:         nuno.brum@gmail.com

@file:          test_spicelib.py
@date:          2022-09-19

@note           spicelib ltsteps + sim_commander + raw_read unit test
                  run ./test/unittests/test_spicelib
"""

import os  # platform independent paths
# ------------------------------------------------------------------------------
# Python Libs
import sys  # python path handling
import unittest  # performs test

#
# Module libs

sys.path.append(
    os.path.abspath((os.path.dirname(os.path.abspath(__file__)) + "/../")))  # add project root to lib search path
from spicelib.log.qspice_log_reader import QspiceLogReader
from spicelib.raw.raw_read import RawRead
from spicelib.editor.spice_editor import SpiceEditor
from spicelib.sim.sim_runner import SimRunner


def has_qspice_detect():
    from spicelib.simulators.qspice_simulator import Qspice
    global qspice_simulator
    qspice_simulator = Qspice
    return qspice_simulator.is_available()


# ------------------------------------------------------------------------------
has_qspice = has_qspice_detect()
skip_qspice_editor_tests = not has_qspice
# print("skip_ltspice_tests", skip_ltspice_tests)
test_dir = '../examples/testfiles/' if os.path.abspath(os.curdir).endswith('unittests') else './examples/testfiles/'
# test_dir = os.path.abspath(test_dir)
print("test_dir", test_dir)
# ------------------------------------------------------------------------------


class test_spicelib(unittest.TestCase):
    """Unnittesting spicelib"""
    # *****************************
    @unittest.skipIf(skip_qspice_editor_tests, "Skip if not in windows environment")
    def test_batch_test(self):
        """
        @note   inits class
        """
        print("Starting test_batch_test")
        from spicelib.simulators.qspice_simulator import Qspice
        # prepare
        self.sim_files = []
        self.measures = {}

        def processing_data(raw_file, log_file):
            print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))
            self.sim_files.append((raw_file, log_file))

        # select spice model
        editor = SpiceEditor(test_dir + "QSPICE_Batch_Test.net")
        runner = SimRunner(parallel_sims=4, output_folder="./output", simulator=Qspice)
        editor.set_parameters(res=0, cap=100e-6)
        editor.set_component_value('R2', '2k')  # Modifying the value of a resistor
        editor.set_component_value('R1', '4k')
        editor.set_element_model('V3', "SINE(0 1 3k 0 0 0)")  # Modifying the

        editor.set_parameter("run", "0")

        for supply_voltage in (5, 10, 15):
            editor.set_component_value('V1', supply_voltage)
            editor.set_component_value('V2', -supply_voltage)
            # overriding the automatic netlist naming
            run_netlist_file = "{}_{}.net".format(editor.circuit_file.name, supply_voltage)
            runner.run(editor, run_filename=run_netlist_file, callback=processing_data)

        runner.wait_completion()
        self.assertEqual(runner.okSim, 3)  # Simulation done with success
        # Sim Statistics
        print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
        self.assertEqual(runner.okSim, 3)
        self.assertEqual(runner.runno, 3)

        # check
        editor.reset_netlist()
        editor.set_element_model('V3', "AC 1 0")
        editor.add_instructions(
                "; Simulation settings",
                ".ac dec 30 1 10Meg",
                ".meas AC GainAC MAX mag(V(out)) ; find the peak response and call it ""Gain""",
                ".meas AC FcutAC TRIG mag(V(out))=GainAC/sqrt(2) FALL=last",
                # ".step param run 0 2 1"
        )

        raw_file, log_file = runner.run_now(editor, run_filename="qspice_no_callback.net")
        print("no_callback", raw_file, log_file)
        log = QspiceLogReader(log_file)
        for measure in log.get_measure_names():
            print(measure, '=', log.get_measure_value(measure))
        self.assertEqual(6.16683e+06, log.get_measure_value('fcutac')[0])
        self.assertEqual(1.99999, log.get_measure_value('gainac')[0])

    @unittest.skipIf(skip_qspice_editor_tests, "Skip if not in windows environment")
    def test_run_from_spice_editor(self):
        """Run command on SpiceEditor"""
        print("Starting test_run_from_spice_editor")
        runner = SimRunner(output_folder='temp' + "temp/", simulator=qspice_simulator)
        # select spice model
        netlist = SpiceEditor(test_dir + "testfile.net")
        # set default arguments
        netlist.set_parameters(res=0.001, cap=100e-6)
        # define simulation
        netlist.add_instructions(
                "; Simulation settings",
                # [".STEP PARAM Rmotor LIST 21 28"],
                ".TRAN 3m",
                # ".step param run 1 2 1"
        )
        # do parameter sweep
        for res in range(5):
            # runner.runs_to_do = range(2)
            netlist.set_parameters(ANA=res)
            raw, log = runner.run(netlist).wait_results()
            print("Raw file '%s' | Log File '%s'" % (raw, log))
        # Sim Statistics
        runner.wait_completion()
        print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
        self.assertEqual(runner.okSim, 5)  # Simulation done with success

    @unittest.skipIf(skip_qspice_editor_tests, "Skip if not in windows environment")
    def test_sim_runner(self):
        """SimRunner and SpiceEditor singletons"""
        print("Starting test_sim_runner")
        # Old legacy class that merged SpiceEditor and SimRunner
        def callback_function(raw_file, log_file):
            print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))

        runner = SimRunner(output_folder='temp' + "temp/", simulator=qspice_simulator)
        SE = SpiceEditor(test_dir + "testfile.net")
        #, parallel_sims=1)
        tstart = 0
        bias_file = ""
        for tstop in (2, 5, 8, 10):
            tduration = tstop - tstart
            SE.add_instruction(".tran {}".format(tduration), )
            if tstart != 0:
                SE.add_instruction(".loadbias {}".format(bias_file))
                # Put here your parameter modifications
                # runner.set_parameters(param1=1, param2=2, param3=3)
            bias_file = test_dir + "sim_loadbias_%d.txt" % tstop
            SE.add_instruction(".savebias {} internal time={}".format(bias_file, tduration))
            tstart = tstop
            runner.run(SE, callback=callback_function)

        SE.reset_netlist()
        SE.add_instruction('.ac dec 40 1m 1G')
        SE.set_component_value('V1', 'AC 1 0')
        runner.run(SE, callback=callback_function)
        runner.wait_completion()
        self.assertEqual(runner.okSim, 5)  # Simulation done with success

    @unittest.skipIf(skip_qspice_editor_tests, "Execute All")
    def test_ltsteps_measures(self):
        """QspiceLogReader Measures from Batch_Test.asc"""
        print("Starting test_ltsteps_measures")
        assert_data = {
            'vout1m'   : [
                -0.0186257,
                -1.04378,
                -1.64283,
                -0.622014,
                1.32386,
                -1.35125,
                -1.88222,
                1.28677,
                1.03154,
                0.953548,
                -0.192821,
                -1.42535,
                0.451607,
                0.0980979,
                1.55525,
                1.66809,
                0.11246,
                0.424023,
                -1.30035,
                0.614292,
                -0.878185,
            ],
            'vin_rms'  : [
                0.706221,
                0.704738,
                0.708225,
                0.707042,
                0.704691,
                0.704335,
                0.704881,
                0.703097,
                0.70322,
                0.703915,
                0.703637,
                0.703558,
                0.703011,
                0.702924,
                0.702944,
                0.704121,
                0.704544,
                0.704193,
                0.704236,
                0.703701,
                0.703436,
            ],
            'vout_rms' : [
                1.41109,
                1.40729,
                1.41292,
                1.40893,
                1.40159,
                1.39763,
                1.39435,
                1.38746,
                1.38807,
                1.38933,
                1.38759,
                1.38376,
                1.37771,
                1.37079,
                1.35798,
                1.33252,
                1.24314,
                1.07237,
                0.875919,
                0.703003,
                0.557131,

            ],
            'gain'     : [
                1.99809,
                1.99689,
                1.99502,
                1.99271,
                1.98894,
                1.98432,
                1.97814,
                1.97336,
                1.97387,
                1.97372,
                1.97202,
                1.9668,
                1.95973,
                1.95012,
                1.93184,
                1.89246,
                1.76445,
                1.52284,
                1.24379,
                0.999007,
                0.792014,
            ],
            'period'   : [
                0.000100148,
                7.95811e-005,
                6.32441e-005,
                5.02673e-005,
                3.99594e-005,
                3.1772e-005,
                2.52675e-005,
                2.01009e-005,
                1.59975e-005,
                1.27418e-005,
                1.01541e-005,
                8.10036e-006,
                6.47112e-006,
                5.18241e-006,
                4.16639e-006,
                3.37003e-006,
                2.75114e-006,
                2.26233e-006,
                1.85367e-006,
                1.50318e-006,
                1.20858e-006,

            ],
            'period_at': [
                0.000100148,
                7.95811e-005,
                6.32441e-005,
                5.02673e-005,
                3.99594e-005,
                3.1772e-005,
                2.52675e-005,
                2.01009e-005,
                1.59975e-005,
                1.27418e-005,
                1.01541e-005,
                8.10036e-006,
                6.47112e-006,
                5.18241e-006,
                4.16639e-006,
                3.37003e-006,
                2.75114e-006,
                2.26233e-006,
                1.85367e-006,
                1.50318e-006,
                1.20858e-006,
            ]
        }
        if has_qspice:
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "QSPICE_Batch_Test.net")
            print(raw_file, log_file)
        else:
            log_file = test_dir + "QSPICE_Batch_Test_1.log"
        log = QspiceLogReader(log_file)
        # raw = RawRead(raw_file)
        for measure in assert_data:
            print("measure", measure)
            for step in range(log.step_count):
                self.assertEqual(log.get_measure_value(measure, step), assert_data[measure][step])

                print(log.get_measure_value(measure, step), assert_data[measure][step])

    @unittest.skipIf(False, "Execute All")
    def test_operating_point(self):
        """Operating Point Simulation Test"""
        print("Starting test_operating_point")
        if has_qspice:
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "DC op point.net")
            self.assertEqual(runner.okSim, 1)  # Simulation done with success
        else:
            raw_file = test_dir + "DC op point_1.qraw"
            # log_file = test_dir + "DC op point_1.log"
        raw = RawRead(raw_file)

        for trace, value_expected  in zip(
                ('V(in)', 'V(out)', 'I(R1)', 'I(R2)', 'I(Vin)'),
                (1.0, 0.5, 5e-05, 5e-05, 5e-05)):
            value_read = raw.get_trace(trace)[0]
            self.assertAlmostEqual(abs(value_read), value_expected, 5, f"mismatch in node {trace}")

    @unittest.skipIf(False, "Execute All")
    def test_operating_point_step(self):
        """Operating Point Simulation with Steps """
        print("Starting test_operating_point_step")
        if has_qspice:
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "DC op point - STEP.net")
        else:
            raw_file = test_dir + "DC op point - STEP_1.qraw"
        raw = RawRead(raw_file)
        vin = raw.get_trace('V(in)')

        for i, b in enumerate(('V(in)', 'V(b4)', 'V(b3)', 'V(b2)', 'V(b1)', 'V(b0)'),):
            meas = raw.get_trace(b)
            for step in range(raw.nPoints):
                self.assertAlmostEqual(meas[step], vin[step] * 2**-i, 7, f"mismatch in node {b}")

    @unittest.skipIf(skip_qspice_editor_tests, "Execute All")
    def test_transient(self):
        """Transient Simulation test """
        print("Starting test_transient")
        if has_qspice:
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "TRAN.net")
        else:
            raw_file = test_dir + "TRAN_1.raw"
            log_file = test_dir + "TRAN_1.log"
        raw = RawRead(raw_file)
        log = QspiceLogReader(log_file)
        vout = raw.get_trace('V(out)')
        meas = ('t1', 't2', 't3', 't4', 't5',)
        time = (1e-3, 2e-3, 3e-3, 4e-3, 5e-3,)
        for m, t in zip(meas, time):
            log_value = log.get_measure_value(m)
            raw_value = vout.get_point_at(t)
            print(log_value, raw_value, log_value - raw_value)
            self.assertAlmostEqual(log_value, raw_value, 2, "Mismatch between log file and raw file")

    @unittest.skipIf(skip_qspice_editor_tests, "Execute All")
    def test_transient_steps(self):
        """Transient simulation with stepped data."""
        print("Starting test_transient_steps")
        if has_qspice:
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "QSPICE_TRAN - STEP.net")
        else:
            raw_file = test_dir + "QSPICE_TRAN - STEP_1.qraw"
            log_file = test_dir + "QSPICE_TRAN - STEP_1.log"

        raw = RawRead(raw_file)
        log = QspiceLogReader(log_file)
        vout = raw.get_trace('V(out)')
        meas = ('t1', 't2', 't3', 't4', 't5',)
        time = (1e-3, 2e-3, 3e-3, 4e-3, 5e-3,)
        for m, t in zip(meas, time):
            for step, step_dict in enumerate(raw.steps):
                log_value = log.get_measure_value(m, step)
                raw_value = vout.get_point_at(t, step)
                self.assertAlmostEqual(log_value, raw_value, 5, f"Mismatch between log file and raw file in step :{step_dict} measure: {m} ")

    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis(self):
        """AC Analysis Test"""
        print("Starting test_ac_analysis")
        from numpy import pi, angle
        if has_qspice:
            editor = SpiceEditor(test_dir + "AC.net")
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(editor)

            R1 = editor.get_component_floatvalue('R1')
            C1 = editor.get_component_floatvalue('C1')
        else:
            raw_file = test_dir + "AC_1.raw"
            log_file = test_dir + "AC_1.log"
            R1 = 100
            C1 = 10E-6
        # Compute the RC AC response with the resistor and capacitor values from the netlist.
        raw = RawRead(raw_file)
        vout_trace = raw.get_trace('V(out)')
        vin_trace = raw.get_trace('V(in)')
        for point, freq in enumerate(raw.axis):
            vout1 = vout_trace.get_point_at(freq)
            vout2 = vout_trace.get_point(point)
            vin = vin_trace.get_point(point)
            self.assertEqual(vout1, vout2)
            self.assertEqual(abs(vin), 1)
            # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
            h = vin / (1 + 2j * pi * freq * R1 * C1)
            self.assertAlmostEqual(abs(vout1), abs(h), 5, f"Difference between theoretical value and simulation at point {point}")
            self.assertAlmostEqual(angle(vout1), angle(h), 5, f"Difference between theoretical value and simulation at point {point}")

    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis_steps(self):
        """AC Analysis Test with steps"""
        print("Starting test_ac_analysis_steps")
        from numpy import pi, angle
        if has_qspice:
            editor = SpiceEditor(test_dir + "AC - STEP.net")
            runner = SimRunner(output_folder='temp', simulator=qspice_simulator)
            raw_file, log_file = runner.run_now(editor)
            C1 = editor.get_component_floatvalue('C1')
        else:
            raw_file = test_dir + "AC - STEP_1.raw"
            log_file = test_dir + "AC - STEP_1.log"
            C1 = 159.1549e-6  # 159.1549uF
        # Compute the RC AC response with the resistor and capacitor values from the netlist.
        raw = RawRead(raw_file)
        vin_trace = raw.get_trace('V(in)')
        vout_trace = raw.get_trace('V(out)')
        for step, step_dict in enumerate(raw.steps):
            R1 = step_dict['r1']
            # print(step, step_dict)
            for point in range(0, raw.get_len(step), 10):  # 10 times less points
                print(point, end=' - ')
                vout = vout_trace.get_point(point, step)
                vin = vin_trace.get_point(point, step)
                freq = raw.axis.get_point(point, step)
                # Calculate the magnitude of the answer Vout = Vin/(1+jwRC)
                h = vin/(1 + 2j * pi * freq * R1 * C1)
                # print(freq, vout, h, vout - h)
                self.assertAlmostEqual(abs(vout), abs(h), 5,
                                       f"Difference between theoretical value ans simulation at point {point}:")
                self.assertAlmostEqual(angle(vout), angle(h), 5,
                                       f"Difference between theoretical value ans simulation at point {point}")

    # 
    # def test_pathlib(self):
    #     """pathlib support"""
    #     import pathlib
    #     DIR = pathlib.Path("../tests")
    #     raw_file = DIR / "AC - STEP_1.raw"
    #     raw = RawRead(raw_file)


# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("Starting tests on spicelib")
    unittest.main()
    print("Tests completed on spicelib")
# ------------------------------------------------------------------------------
