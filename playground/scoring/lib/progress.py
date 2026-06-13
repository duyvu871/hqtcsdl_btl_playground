"""CLI progress — wrapper mỏng trên Rich."""

from __future__ import annotations
from rich.console import Console

class Progress:
    """Giữ API log/bar hiện tại; render bằng Rich."""
    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet
        self._console = Console(stderr=True, quiet=quiet)

    def log(self, msg: str) -> None:
        if not self.quiet:
            self._console.print(msg)