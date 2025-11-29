#!/usr/bin/env python

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        sweep_iterators_unitest.py
# Purpose:     Tool used validate the sweep_iterators.py module
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

# Python Libs
import sys        # python path handling
import os         # platform independent paths
import unittest   # performs test
#
# Module libs
sys.path.append(os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../"))   # add project root to lib search path
from spicelib.utils.sweep_iterators import sweep, sweep_n, sweep_log, sweep_log_n  # Python Script under test
#------------------------------------------------------------------------------


class test_sweep_iterators(unittest.TestCase):


    def test_iterator_objects(self):
        """
        @note  iterator_objects
        """
        # *****************************
        # check
        self.assertListEqual(list(sweep(10)), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertListEqual(list(sweep(1, 8)), [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertListEqual(list(sweep(2, 8, 2)), [2, 4, 6, 8])
        self.assertListEqual(list(sweep(2, 8, -2)), [8, 6, 4, 2])
        self.assertListEqual(list(sweep(8, 2, 2)), [8, 6, 4, 2])
        self.assertListEqual(list(sweep(0.3, 1.1, 0.2)), [0.3, 0.5, 0.7, 0.9000000000000001, 1.1])
        self.assertListEqual(list(sweep(15, -15, 2.5)),
                             [15.0, 12.5, 10.0, 7.5, 5.0, 2.5, 0.0, -2.5, -5.0, -7.5, -10.0, -12.5, -15.0])
        self.assertListEqual(list(sweep(-2, 2, 2)), [-2, 0, 2])
        self.assertListEqual(list(sweep(-2, 2, -2)), [2, 0, -2])
        self.assertListEqual(list(sweep(2, -2, 2)), [2, 0, -2])
        self.assertListEqual(list(sweep(2, -2, -2)), [2, 0, -2])
        self.assertListEqual(list(sweep_n(0.3, 1.1, 5)), [0.3, 0.5, 0.7, 0.9000000000000001, 1.1])
        self.assertListEqual(list(sweep_n(15, -15, 13)),
                             [15.0, 12.5, 10.0, 7.5, 5.0, 2.5, 0.0, -2.5, -5.0, -7.5, -10.0, -12.5, -15.0])
        self.assertListEqual(list(sweep_log(0.1, 11e3, 10)), [0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0])
        self.assertListEqual(list(sweep_log(1000, 1, 2)),
                             [1000, 500.0, 250.0, 125.0, 62.5, 31.25, 15.625, 7.8125, 3.90625, 1.953125])
        for a, b in zip(list(sweep_log_n(1, 10, 6)),
                             [1.0, 1.584893192461113, 2.5118864315095806, 3.981071705534973, 6.309573444801934,
                              10.0]):

            self.assertAlmostEqual(a, b)
        for a, b in zip(list(sweep_log_n(10, 1, 5)),
                             [10.0, 5.623413251903491, 3.1622776601683795, 1.7782794100389228, 1]):
            self.assertAlmostEqual(a, b)


#------------------------------------------------------------------------------
if __name__ == '__main__':
    unittest.main()
#------------------------------------------------------------------------------
