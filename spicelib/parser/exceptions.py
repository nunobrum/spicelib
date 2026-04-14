"""Parser-related exceptions."""


class ParserError(Exception):
	"""General parser error wrapper."""
	pass


class DialectError(ParserError):
	"""Raised when a dialect is missing or invalid."""
	pass


class FallbackError(ParserError):
	"""Raised when a fallback parser fails."""
	pass


