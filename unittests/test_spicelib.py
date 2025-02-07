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
# Name:        test_spicelib.py
# Purpose:     Tool used to launch Spice simulation in batch mode. Netlsts can
#              be updated by user instructions
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
@email:         me@nunobrum.com

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
from spicelib.log.ltsteps import LTSpiceLogReader
from spicelib.raw.raw_read import RawRead
from spicelib.editor.spice_editor import SpiceEditor
from spicelib.sim.sim_runner import SimRunner


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
if os.path.abspath(os.curdir).endswith('unittests'):
    test_dir = '../examples/testfiles/'
    temp_dir = '../examples/testfiles/temp/'
else:
    test_dir = './examples/testfiles/'
    temp_dir = './examples/testfiles/temp/'

print("test_dir", test_dir)
# ------------------------------------------------------------------------------


class test_spicelib(unittest.TestCase):
    """Unnittesting spicelib"""
    # *****************************
    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_batch_test(self):
        """
        @note   inits class
        """
        print("Starting test_batch_test")
        from spicelib.simulators.ltspice_simulator import LTspice
        # prepare
        self.sim_files = []
        self.measures = {}

        def processing_data(raw_file, log_file):
            print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))
            self.sim_files.append((raw_file, log_file))

        # select spice model
        LTspice.create_netlist(test_dir + "Batch_Test.asc", exe_log=hide_exe_print_statements)
        editor = SpiceEditor(test_dir + "Batch_Test.net")
        runner = SimRunner(parallel_sims=4, output_folder="./output", simulator=LTspice)
        editor.set_parameters(res=0, cap=100e-6)
        editor.set_component_value('R2', '2k')  # Modifying the value of a resistor
        editor.set_component_value('R1', '4k')
        editor.set_element_model('V3', "SINE(0 1 3k 0 0 0)")  # Modifying the
        editor.set_component_value('XU1:C2', 20e-12)  # modifying a cap inside a component
        # define simulation
        editor.add_instructions(
                "; Simulation settings",
                # ".step dec param freq 10k 1Meg 10",
        )
        editor.set_parameter("run", "0")

        for opamp in ('AD712', 'AD820_XU1'):  # don't use AD820, it is defined in the file and will mess up newer LTspice versions
            editor.set_element_model('XU1', opamp)
            for supply_voltage in (5, 10, 15):
                editor.set_component_value('V1', supply_voltage)
                editor.set_component_value('V2', -supply_voltage)
                # overriding the automatic netlist naming
                run_netlist_file = "{}_{}_{}.net".format(editor.circuit_file.name, opamp, supply_voltage)
                runner.run(editor, run_filename=run_netlist_file, callback=processing_data, exe_log=hide_exe_print_statements)

        runner.wait_completion()

        # Sim Statistics
        print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
        self.assertEqual(runner.okSim, 6)
        self.assertEqual(runner.runno, 6)

        # check
        editor.reset_netlist()
        editor.set_element_model('XU1', 'AD712')  # this is needed with the newer LTspice versions, as AD820 has been defined in the file and in a lib
        editor.remove_instruction('.meas TRAN period FIND time WHEN V(out)=0 RISE=1')  # not in TRAN now
        editor.remove_instruction('.meas Vout1m FIND V(OUT) AT 1m')  # old style, not working on AC with these frequencies
        
        editor.set_element_model('V3', "AC 1 0")
        editor.add_instructions(
                "; Simulation settings",
                ".ac dec 30 1 10Meg",
                ".meas AC GainAC MAX mag(V(out)) ; find the peak response and call it ""Gain""",
                ".meas AC FcutAC TRIG mag(V(out))=GainAC/sqrt(2) FALL=last",
                ".meas AC Vout1m FIND V(out) AT 1Hz"
        )

        raw_file, log_file = runner.run_now(editor, run_filename="no_callback.net", exe_log=hide_exe_print_statements)
        print("no_callback", raw_file, log_file)
        log = LTSpiceLogReader(log_file)
        for measure in log.get_measure_names():
            print(measure, '=', log.get_measure_value(measure))
        print("vout1m.mag_db=", log.get_measure_value('vout1m').mag_db())
        print("vout1m.ph=", log.get_measure_value('vout1m').ph)
        
        self.assertAlmostEqual(log.get_measure_value('fcutac'), 6.3e+06, delta=0.1e6)  # have to be imprecise, different ltspice versions give different replies
        # self.assertEqual(log.get_measure_value('vout1m'), 1.9999977173843142 - 1.8777417486008045e-09j)  # excluded, diffifult to make compatible
        self.assertAlmostEqual(log.get_measure_value('vout1m').mag_db(), 6.0206, delta=0.0001)
        self.assertAlmostEqual(log.get_measure_value('vout1m').ph, -1.7676e-05, delta=0.0001e-05)

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_run_from_spice_editor(self):
        """Run command on SpiceEditor"""
        print("Starting test_run_from_spice_editor")
        runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
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
            raw, log = runner.run(netlist, exe_log=hide_exe_print_statements).wait_results()
            print("Raw file '%s' | Log File '%s'" % (raw, log))
        runner.wait_completion()
        # Sim Statistics
        print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
        self.assertEqual(runner.okSim, 5)
        self.assertEqual(runner.runno, 5)

    @unittest.skipIf(skip_ltspice_tests, "Skip if not in windows environment")
    def test_sim_runner(self):
        """SimRunner and SpiceEditor singletons"""
        print("Starting test_sim_runner")
        # Old legacy class that merged SpiceEditor and SimRunner

        def callback_function(raw_file, log_file):
            print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))

        # Forcing to use only one simulation at a time so that the bias file is created before
        # the next simulation is called. Alternatively, wait_completion() can be called after each run
        # or use run_now and call the callback_function manually.
        runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator, parallel_sims=1)
        # select spice model
        SE = SpiceEditor(test_dir + "testfile.net")
        tstart = 0
        bias_file = ""
        for tstop in (2, 5, 8, 10):
            SE.reset_netlist()  # Reset the netlist to the original status
            tduration = tstop - tstart
            SE.add_instruction(".tran {}".format(tduration), )
            if tstart != 0:
                SE.add_instruction(".loadbias {}".format(bias_file))
                # Put here your parameter modifications
                # runner.set_parameters(param1=1, param2=2, param3=3)
            bias_file = "sim_loadbias_%d.txt" % tstop            
            SE.add_instruction(".savebias {} internal time={}".format(bias_file, tduration))
            tstart = tstop
            runner.run(SE, callback=callback_function, exe_log=hide_exe_print_statements)

        SE.reset_netlist()
        SE.add_instruction('.ac dec 40 1m 1G')
        SE.set_component_value('V1', 'AC 1 0')
        runner.run(SE, callback=callback_function, exe_log=hide_exe_print_statements)
        runner.wait_completion()
        
        # Sim Statistics
        print('Successful/Total Simulations: ' + str(runner.okSim) + '/' + str(runner.runno))
        self.assertEqual(runner.okSim, 5)
        self.assertEqual(runner.runno, 5)        

    @unittest.skipIf(False, "Execute All")
    def test_ltsteps_measures(self):
        """LTSpiceLogReader Measures from Batch_Test.asc"""
        print("Starting test_ltsteps_measures")
        assert_data = {
            'vout1m': [
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
            'vin_rms': [
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
            'vout_rms': [
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
            'gain': [
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
            'period': [
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
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "Batch_Test_Simple.asc", exe_log=hide_exe_print_statements)
            print(raw_file, log_file)
            self.assertIsNotNone(raw_file, "Batch_Test_Simple.asc run failed")
        else:
            log_file = test_dir + "Batch_Test_Simple_1.log"
        log = LTSpiceLogReader(log_file)
        
        self.assertEqual(log.step_count, 21, "Batch_Test_Simple step_count is wrong") 
        # raw = RawRead(raw_file)
        for measure in assert_data:
            print("measure", measure)
            for step in range(log.step_count):
                print(log.get_measure_value(measure, step), assert_data[measure][step])
                self.assertAlmostEqual(log.get_measure_value(measure, step), assert_data[measure][step], places=1)  # TODO the reference data should be adapted, is too imprecise

    @unittest.skipIf(False, "Execute All")
    def test_operating_point(self):
        """Operating Point Simulation Test"""
        print("Starting test_operating_point")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "DC op point.asc", exe_log=hide_exe_print_statements)
        else:
            raw_file = test_dir + "DC op point_1.raw"
            # log_file = test_dir + "DC op point_1.log"
        raw = RawRead(raw_file)
        traces = [raw.get_trace(trace)[0] for trace in sorted(raw.get_trace_names())]
        self.assertListEqual(traces, [4.999999873689376e-05, 4.999999873689376e-05, -4.999999873689376e-05, 1.0, 0.5], "Lists are different")

    @unittest.skipIf(False, "Execute All")
    def test_operating_point_step(self):
        """Operating Point Simulation with Steps """
        print("Starting test_operating_point_step")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "DC op point - STEP.asc", exe_log=hide_exe_print_statements)
        else:
            raw_file = test_dir + "DC op point - STEP_1.raw"
        raw = RawRead(raw_file)
        vin = raw.get_trace('V(in)')

        for i, b in enumerate(('V(in)', 'V(b4)', 'V(b3)', 'V(b2)', 'V(b1)', 'V(out)'),):
            meas = raw.get_trace(b)
            for step in range(raw.nPoints):
                self.assertEqual(meas[step], vin[step] * 2**-i)

    @unittest.skipIf(False, "Execute All")
    def test_transient(self):
        """Transient Simulation test """
        print("Starting test_transient")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "TRAN.asc", exe_log=hide_exe_print_statements)
        else:
            raw_file = test_dir + "TRAN_1.raw"
            log_file = test_dir + "TRAN_1.log"
        raw = RawRead(raw_file)
        log = LTSpiceLogReader(log_file)
        vout = raw.get_trace('V(out)')
        meas = ('t1', 't2', 't3', 't4', 't5',)
        time = (1e-3, 2e-3, 3e-3, 4e-3, 5e-3,)
        for m, t in zip(meas, time):
            log_value = log.get_measure_value(m)
            raw_value = vout.get_point_at(t)
            print(log_value, raw_value, log_value - raw_value)
            self.assertAlmostEqual(log_value, raw_value, 2, "Mismatch between log file and raw file")

    @unittest.skipIf(False, "Execute All")
    def test_transient_steps(self):
        """Transient simulation with stepped data."""
        print("Starting test_transient_steps")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "TRAN - STEP.asc", exe_log=hide_exe_print_statements)
        else:
            raw_file = test_dir + "TRAN - STEP_1.raw"
            log_file = test_dir + "TRAN - STEP_1.log"

        raw = RawRead(raw_file)
        log = LTSpiceLogReader(log_file)
        vout = raw.get_trace('V(out)')
        meas = ('t1', 't2', 't3', 't4', 't5',)
        time = (1e-3, 2e-3, 3e-3, 4e-3, 5e-3,)
        for m, t in zip(meas, time):
            print(m)
            for step, step_dict in enumerate(raw.steps):
                log_value = log.get_measure_value(m, step)
                raw_value = vout.get_point_at(t, step)
                print(step, step_dict, log_value, raw_value, log_value - raw_value)
                self.assertAlmostEqual(log_value, raw_value, 2, f"Mismatch between log file and raw file in step :{step_dict} measure: {m} ")

    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis(self):
        """AC Analysis Test"""
        
        def checkresults(raw_file: str, R1: float, C1: float):
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
                self.assertAlmostEqual(abs(vout1), abs(h), places=5, msg=f"{raw_file}: Difference between theoretical value ans simulation at point {point}")
                self.assertAlmostEqual(angle(vout1), angle(h), places=5, msg=f"{raw_file}: Difference between theoretical value ans simulation at point {point}")
        
        print("Starting test_ac_analysis")
        from numpy import pi, angle
        if has_ltspice:
            from spicelib.editor.asc_editor import AscEditor
            editor = AscEditor(test_dir + "AC.asc")
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(editor, exe_log=hide_exe_print_statements)

            R1 = editor.get_component_floatvalue('R1')
            C1 = editor.get_component_floatvalue('C1')
        else:
            raw_file = test_dir + "AC_1.raw"
            # log_file = test_dir + "AC_1.log"
            R1 = 100
            C1 = 10E-6
        checkresults(raw_file, R1, C1)
        
        raw_file = test_dir + "AC_1.ascii.raw"
        R1 = 100
        C1 = 10E-6
        checkresults(raw_file, R1, C1)
        
    @unittest.skipIf(False, "Execute All")
    def test_ac_analysis_steps(self):
        """AC Analysis Test with steps"""
        print("Starting test_ac_analysis_steps")
        from numpy import pi, angle
        if has_ltspice:
            from spicelib.editor.asc_editor import AscEditor
            editor = AscEditor(test_dir + "AC - STEP.asc")
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(editor, exe_log=hide_exe_print_statements)
            C1 = editor.get_component_floatvalue('C1')
        else:
            raw_file = test_dir + "AC - STEP_1.raw"
            # log_file = test_dir + "AC - STEP_1.log"
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
                h = vin / (1 + 2j * pi * freq * R1 * C1)
                # print(freq, vout, h, vout - h)
                self.assertAlmostEqual(abs(vout), abs(h), 5,
                                       f"Difference between theoretical value ans simulation at point {point}:")
                self.assertAlmostEqual(angle(vout), angle(h), 5,
                                       f"Difference between theoretical value ans simulation at point {point}")
        print(" end")                

    @unittest.skipIf(False, "Execute All")
    def test_fourier_log_read(self):
        """Fourier Analysis Test"""
        print("Starting test_fourier_log_read")
        if has_ltspice:
            runner = SimRunner(output_folder=temp_dir, simulator=ltspice_simulator)
            raw_file, log_file = runner.run_now(test_dir + "Fourier_30MHz.asc", exe_log=hide_exe_print_statements)
        else:
            raw_file = test_dir + "Fourier_30MHz_1.raw"
            log_file = test_dir + "Fourier_30MHz_1.log"
        raw = RawRead(raw_file)
        log = LTSpiceLogReader(log_file)
        print(log.fourier)
        tmax = max(raw.get_time_axis())
        dc_component = raw.get_wave('V(a)').mean()
        fundamental = log.fourier['V(a)'][0].fundamental
        self.assertEqual(fundamental, 30E6, "Fundamental frequency is not 30MHz")
        n_periods_calc = tmax * fundamental
        self.assertAlmostEqual(log.fourier['V(a)'][0].n_periods, n_periods_calc, 5, "Mismatch in calculated number of periods")
        self.assertAlmostEqual(log.fourier['V(a)'][0].dc_component, dc_component, 2, "Mismatch in DC component")
        self.assertEqual(len(log.fourier['V(a)'][0].harmonics), 9, "Mismatch in requested number of harmonics")

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
