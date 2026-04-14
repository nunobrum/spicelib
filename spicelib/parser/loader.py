"""Grammar loader and compile helpers for Lark."""
from pathlib import Path
from typing import Optional


def _require_lark():
	try:
		from lark import Lark
		return Lark
	except Exception:
		raise ImportError("Install 'lark-parser' (pip install lark-parser)")


def read_grammar_file(path: Path) -> str:
	with path.open("r", encoding="utf-8") as f:
		return f.read()


def compile_grammar_from_text(grammar_text: str):
	"""Compile a Lark grammar string and return a Lark parser instance.

	Uses LALR by default for speed. Propagates positions so transformers can access meta info.
	"""
	Lark = _require_lark()
	kwargs = {"parser": "lalr", "propagate_positions": True}
	# Some versions of lark accept a `filename` parameter to help resolve
	# %import statements relative to a file. Older/newer versions may not
	# accept it. Try passing it and fall back to calling without if the
	# constructor rejects the keyword.
	return Lark(grammar_text, **kwargs)


def compile_grammar_from_file(grammar_path: Path):
	text = read_grammar_file(grammar_path)
	return compile_grammar_from_text(text)


