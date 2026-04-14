"""Transform Lark parse trees into simple Python dicts (AST-like)."""
from typing import Any

try:
    from lark import Transformer, Token
except Exception:  # pragma: no cover - lark not installed
    Transformer = None
    Token = None


if Transformer is None:  # pragma: no cover - runtime guard
    def _missing_lark(*a, **k):
        raise ImportError("lark-parser is required for lark_transformer. Install with: pip install lark-parser")


    class BaseTransformer:
        def __init__(self, *a, **k):
            _missing_lark()

        def transform(self, *a, **k):
            _missing_lark()


else:
    class BaseTransformer(Transformer):
        def DESIGNATOR(self, tok: Token):
            return str(tok)

        def NODE(self, tok: Token):
            return str(tok)

        def DIRECTIVE(self, tok: Token):
            return str(tok)

        def ARGUMENTS(self, tok: Token):
            return str(tok).strip()

        def COMMENT(self, tok: Token):
            s = str(tok)
            return s[1:] if s.startswith(";") else s

        def nodes(self, items):
            return items

        def value(self, items):
            return str(items[0]).strip() if items else None

        def component_line(self, items):
            designator = items[0] if items else None
            nodes = items[1] if len(items) >= 2 else []
            value = items[2] if len(items) >= 3 else None
            return {"type": "component", "designator": designator, "nodes": nodes, "value": value}

        def directive_line(self, items):
            directive = items[0] if items else None
            args = items[1] if len(items) > 1 else None
            return {"type": "directive", "directive": directive, "args": args}

        def comment_line(self, items):
            return {"type": "comment", "text": items[0] if items else ""}

        def start(self, items):
            return [i for i in items if i is not None]

