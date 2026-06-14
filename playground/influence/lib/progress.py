"""Logging/progress helper nhỏ cho CLI."""

from __future__ import annotations

try:
    from rich.console import Console
except Exception:  # pragma: no cover
    Console = None  # type: ignore


class Progress:
    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet
        self._console = Console(stderr=True, quiet=quiet) if Console else None

    def log(self, message: str) -> None:
        if self.quiet:
            return
        if self._console:
            self._console.print(message)
        else:
            print(message)
