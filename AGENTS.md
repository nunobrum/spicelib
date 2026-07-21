# AGENTS.md — Guidance for AI Coding Agents

This file provides context for AI coding agents (e.g. GitHub Copilot, Codex) working in the **spicelib** repository.

---

## Repository Overview

**spicelib** is a Python library (GPLv3) that provides a toolchain for automating SPICE circuit simulations. It targets LTspice, Ngspice, QSPICE, and Xyce simulators.

Key capabilities:
- Read and write SPICE raw waveform files (`.raw`)
- Edit SPICE netlists (`.net`/`.cir`), LTspice schematics (`.asc`), and QSPICE schematics (`.qsch`)
- Run simulations in batch/parallel mode
- Perform Monte Carlo, worst-case, and sensitivity analyses
- CLI tools: `ltsteps`, `histogram`, `rawplot`, `run_server`, `asc_to_qsch`, `raw_convert`

---

## Project Layout

```
spicelib/               # Main Python package
  __init__.py           # Public API re-exports (RawRead, RawWrite, SpiceEditor, AscEditor, QschEditor, SimRunner)
  editor/               # Netlist and schematic editors
    base_editor.py      # Abstract base for all editors
    spice_editor.py     # Generic SPICE netlist editor
    asc_editor.py       # LTspice .asc schematic editor
    qsch_editor.py      # QSPICE .qsch schematic editor
  raw/                  # Raw waveform file I/O
    raw_read.py         # RawRead class
    raw_write.py        # RawWrite class
    plot_data.py        # PlotData class
    raw_classes.py      # Shared data structures and exceptions
  sim/                  # Simulation orchestration
    sim_runner.py       # SimRunner — parallel batch simulation
    sim_stepping.py     # SimStepper — parameter stepping
    simulator.py        # Abstract Simulator base class
    tookit/             # Analysis toolkit
      montecarlo.py
      worst_case.py
      fast_worst_case.py
      sim_analysis.py
  simulators/           # Concrete simulator integrations
    ltspice_simulator.py
    ngspice_simulator.py
    qspice_simulator.py
    xyce_simulator.py
  client_server/        # Distributed simulation (SimServer / SimClient)
  scripts/              # CLI entry points (ltsteps, histogram, rawplot, …)
  log/                  # Log file parsers
  utils/                # Shared utilities
unittests/              # Test suite (unittest-based)
doc/                    # Sphinx documentation source
examples/               # Usage examples
```

---

## Environment Setup

The project uses [Poetry](https://python-poetry.org/) for dependency management.

```bash
# Install runtime and dev dependencies
pip install poetry
poetry install

# Or install just the runtime deps with pip
pip install numpy scipy psutil matplotlib
```

Python **3.10+** is required.

---

## Running Tests

Tests use Python's built-in `unittest` framework. Run them directly — there is no pytest configuration.

```bash
# Run the full test suite (mirrors CI)
python unittests/sweep_iterators_unittest.py
python unittests/test_spicelib.py
python unittests/test_qspice_rawread.py
python unittests/test_spice_editor.py
python unittests/test_asc_editor.py
python unittests/test_qsch_editor.py
python unittests/test_rawreaders.py
python unittests/test_raw_write.py
```

CI runs on `ubuntu-latest` with Python 3.10 (x64) on every push (`.github/workflows/unittest.yml`).

Note: Tests that exercise actual simulators (LTspice, Ngspice, QSPICE, Xyce) are skipped automatically when the simulator executables are not present on the system.

---

## Build & Distribution

```bash
# Build the wheel
poetry build           # or: make dist

# Build HTML documentation (requires Sphinx)
make doc

# Install locally from built wheel
make install
```

---

## Coding Conventions

- **Style**: Standard Python; no project-specific linter configuration is present. Follow PEP 8.
- **Type hints**: Used throughout the codebase — add them to new code.
- **Docstrings**: Public classes and methods use reStructuredText-style docstrings (Sphinx-compatible).
- **Logging**: Each module creates a logger named `spicelib.<ModuleName>`. Use `logging.getLogger("spicelib.<ModuleName>")` — do **not** use `print()` for diagnostic output.
- **Exceptions**: Raise domain-specific exceptions (e.g. `SpiceReadException` from `raw_classes.py`, `EditorFileTypeError` from `editor_errors.py`).
- **No secrets / credentials** should ever be committed. Simulator paths are discovered at runtime or passed by the user.

---

## Key Abstractions

| Class | Location | Purpose |
|---|---|---|
| `SpiceEditor` | `editor/spice_editor.py` | Read/write/modify generic SPICE netlists |
| `AscEditor` | `editor/asc_editor.py` | Read/write LTspice `.asc` schematics |
| `QschEditor` | `editor/qsch_editor.py` | Read/write QSPICE `.qsch` schematics |
| `SimRunner` | `sim/sim_runner.py` | Parallel batch simulation orchestration |
| `SimStepper` | `sim/sim_stepping.py` | Multi-dimensional parameter sweeps |
| `RawRead` | `raw/raw_read.py` | Parse SPICE `.raw` waveform files |
| `RawWrite` | `raw/raw_write.py` | Write SPICE `.raw` waveform files |
| `Simulator` | `sim/simulator.py` | Abstract base; subclasses in `simulators/` |

---

## Adding a New Simulator

1. Create `spicelib/simulators/<name>_simulator.py`.
2. Subclass `spicelib.sim.simulator.Simulator` and implement all abstract methods.
3. Register the logger name in `spicelib/__init__.py` → `all_loggers()`.
4. Add integration tests in `unittests/`.

---

## Adding a New Editor

1. Subclass `spicelib.editor.base_editor.BaseEditor` (or `BaseSchematic` for graphical formats).
2. Implement the required abstract methods for reading/writing the file format.
3. Re-export the new class from `spicelib/__init__.py` if it is part of the public API.
4. Add tests in `unittests/`.

---

## Pull Requests & Contribution

- Target the `main` branch.
- Ensure all existing unit tests pass before opening a PR.
- Add tests for new functionality in the `unittests/` directory, following the existing `unittest.TestCase` pattern.
- Update `README.md` and/or `doc/` if public-facing behaviour changes.
