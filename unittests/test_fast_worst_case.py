#!/usr/bin/env python

"""Regression tests for the fast worst-case search algorithm."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spicelib.log.logfile_data import LogfileData
from spicelib.sim.tookit.fast_worst_case import FastWorstCaseAnalysis


class TestFastWorstCaseAnalysis(unittest.TestCase):
    def test_restarts_maximum_validation_after_wrong_assumption(self) -> None:
        component_values: dict[str, str | float] = {"R1": "10"}
        editor = Mock()
        editor.get_components.side_effect = (
            lambda prefix=None: ["R1"] if prefix in (None, "R") else []
        )
        editor.get_component_value.side_effect = lambda ref: component_values[ref]
        editor.set_component_value.side_effect = (
            lambda ref, value: component_values.__setitem__(ref, value)
        )
        editor.reset_netlist.side_effect = lambda: component_values.__setitem__("R1", "10")

        measurements = iter((0.0, 1.0, 2.0, 1.0, 1.0, 2.0))
        runner = Mock()
        runner.run.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
            retcode=0,
            measurement=next(measurements),
        )

        analysis = FastWorstCaseAnalysis(editor, runner)
        analysis.set_tolerance("R1", 0.1)

        def read_logfile(task: SimpleNamespace) -> LogfileData:
            return LogfileData(dataset={"gain": [task.measurement]})

        with patch.object(analysis, "read_logfile", side_effect=read_logfile):
            nominal, min_value, max_values, max_value, min_values = analysis.run_analysis(
                measure="gain",
            )

        self.assertEqual(nominal, 0.0)
        self.assertEqual(max_value, 2.0)
        self.assertEqual(min_value, 1.0)
        self.assertAlmostEqual(max_values["R1"], 9.0)
        self.assertAlmostEqual(min_values["R1"], 11.0)
        self.assertEqual(runner.run.call_count, 6)
        runner.cleanup_files.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
