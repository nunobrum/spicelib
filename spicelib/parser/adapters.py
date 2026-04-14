"""Adapter helpers to call the new Lark parser while preserving older signatures.

This module provides thin shims that mirror common functions from the old regex-based
API and delegate to the new Parser. It also supports a `use_lark` flag to allow
falling back to the legacy parser later.
"""
from typing import Any

from . import __init__ as _api
from .exceptions import ParserError


def parse_netlist(text: str, dialect: str = "base", use_lark: bool = True) -> Any:
    """Parse a netlist and return an AST-like structure.

    If `use_lark` is False, this will raise NotImplementedError for now; in the
    future it should call the legacy regex parser.
    """
    if not use_lark:
        raise NotImplementedError("Regex fallback not implemented yet. Use use_lark=True")
    try:
        return _api.parse(text, dialect=dialect)
    except ParserError:
        # In future, call legacy parser as fallback here.
        raise

