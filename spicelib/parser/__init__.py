"""spicelib.parser

Minimal Lark-based parser public API and Parser class.
"""
from __future__ import annotations

from typing import Optional, List, Any

from . import dialects
from .lark_transformer import BaseTransformer
from .exceptions import ParserError


class Parser:
    """High-level parser that wraps a compiled Lark grammar and a Transformer.

    Use Parser.parse(text) to get a list of parsed line dicts.
    """

    def __init__(self, dialect: str = "base") -> None:
        self.dialect = dialect
        self._grammar = dialects.get_compiled_grammar(dialect)
        if self._grammar is None:
            raise ParserError(f"Dialect '{dialect}' is not registered")
        self._transformer = BaseTransformer()

    def parse(self, text: str, filename: Optional[str] = None) -> List[Any]:
        """Parse a netlist text and return a list of line dicts (AST-like).

        Raises ParserError on failure.
        """
        try:
            tree = self._grammar.parse(text)
            result = self._transformer.transform(tree)
            return result
        except Exception as exc:
            # Wrap Lark exceptions in ParserError with context
            raise ParserError(str(exc)) from exc


# Convenience functions
# Do not instantiate a default Parser at import time (dialects may not be ready)
_default_parser = None


def parse(text: str, dialect: str = "base") -> List[Any]:
    p = Parser(dialect=dialect)
    return p.parse(text)


def list_dialects() -> List[str]:
    return dialects.list_dialects()

