"""Dialect registry with lazy compilation of built-in grammars.

This module registers grammar file paths at import time (no Lark dependency)
and compiles them on demand when a parser requests a dialect. This avoids
raising import-time errors when `lark-parser` is not installed in the
environment.
"""

from pathlib import Path
from typing import Dict, Optional

from . import loader

# Two registries:
# - _compiled: name -> compiled Lark parser (compiled object)
# - _paths: name -> Path to grammar file (to lazily compile on demand)
_compiled: Dict[str, object] = {}
_paths: Dict[str, Path] = {}

GRAMMAR_DIR = Path(__file__).parent / "grammar"


def register_dialect(name: str, compiled_grammar) -> None:
    """Register an already compiled Lark parser for a dialect name."""
    _compiled[name] = compiled_grammar


def register_dialect_path(name: str, path: Path) -> None:
    """Register a grammar file path for lazy compilation later."""
    _paths[name] = path


def get_compiled_grammar(name: str):
    """Return a compiled grammar for `name`, compiling lazily if necessary.

    Returns None if no grammar is available for the name.
    """
    if name in _compiled:
        return _compiled[name]
    path = _paths.get(name)
    if path is None:
        return None
    # Try to compile now (may raise ImportError if lark missing)
    compiled = loader.compile_grammar_from_file(path)
    _compiled[name] = compiled
    return compiled


def list_dialects():
    # union of registered compiled grammars and registered paths
    names = set(_compiled.keys()) | set(_paths.keys())
    return list(names)


def _register_builtins():
    """Scan the grammar dir and register available grammar files as paths.

    Actual compilation is deferred until get_compiled_grammar is called.
    """
    if not GRAMMAR_DIR.exists():
        return
    # Map expected builtin names to filenames
    builtins = {"base": "base.lark", "ltspice": "ltspice.lark"}
    for name, fname in builtins.items():
        p = GRAMMAR_DIR / fname
        if p.exists():
            register_dialect_path(name, p)


# Register builtin grammar paths at import time (no Lark dependency required)
_register_builtins()

