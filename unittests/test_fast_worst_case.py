#!/usr/bin/env python

"""Regression tests for the fast worst-case search algorithm."""

import sys
import unittest
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spicelib.sim.tookit.fast_worst_case import FastWorstCaseAnalysis
from spicelib.sim.tookit.tolerance_deviations import ComponentDeviation


class _LogData:
    def __init__(self, values: Sequence[float]) -> None:
        self.values = values

    def get_measure_value(self, _measure: str, run: int | None = None) -> float:
        return self.values[0] if run is None else self.values[run]


class _Editor:
    def __init__(self) -> None:
        self.values: dict[str, str | float] = {"R1": "10"}

    def get_component_value(self, ref: str) -> str | float:
        return self.values[ref]

    def set_component_value(self, ref: str, value: str | float) -> None:
        self.values[ref] = value

    def reset_netlist(self) -> None:
        self.values["R1"] = "10"


class _FastWorstCaseHarness(FastWorstCaseAnalysis):
    """Run the search with deterministic measurements and no simulator."""

    def __init__(self) -> None:
        self.editor = _Editor()
        self.simulations = []
        self.simulation_results = {}
        self.elements_analysed = []
        self.device_deviations = {
            "R1": ComponentDeviation.from_tolerance(0.1),
        }
        self.parameter_deviations = {}
        self.default_tolerance = {}
        self.analysis_executed = False
        self.testbench_executed = False
        self._validation_values = iter((2.0, 1.0, 1.0, 2.0))

    def clear_simulation_data(self) -> None:
        self.simulations.clear()
        self.simulation_results.clear()
        self.analysis_executed = False

    def _reset_netlist(self) -> None:
        self.editor.reset_netlist()

    def reset_netlist(self) -> None:
        self._reset_netlist()

    def play_instructions(self) -> None:
        pass

    def run(self, **_kwargs: Any) -> object:
        return object()

    def wait_completion(self) -> None:
        pass

    def read_logfiles(self) -> _LogData:
        return _LogData((0.0, 1.0))

    def add_log(self, _task: object) -> _LogData:
        return _LogData((next(self._validation_values),))

    def cleanup_files(self) -> None:
        pass


class TestFastWorstCaseAnalysis(unittest.TestCase):
    def test_restarts_maximum_validation_after_wrong_assumption(self) -> None:
        analysis = _FastWorstCaseHarness()

        nominal, min_value, max_values, max_value, min_values = analysis.run_analysis(
            measure="gain",
        )

        self.assertEqual(nominal, 0.0)
        self.assertEqual(max_value, 2.0)
        self.assertEqual(min_value, 1.0)
        self.assertAlmostEqual(max_values["R1"], 9.0)
        self.assertAlmostEqual(min_values["R1"], 11.0)


if __name__ == "__main__":
    unittest.main()
