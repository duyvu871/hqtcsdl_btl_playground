"""CLI progress — wrapper mỏng trên Rich (https://rich.readthedocs.io/)."""

from __future__ import annotations

from rich.console import Console
from rich.progress import BarColumn, Progress as RichProgress, TaskProgressColumn, TextColumn


class Progress:
    """Giữ API log/bar hiện tại; render bằng Rich."""

    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet
        self._console = Console(stderr=True, quiet=quiet)
        self._progress: RichProgress | None = None
        self._task_id: int | None = None
        self._task_total: int = 0

    def log(self, msg: str) -> None:
        if not self.quiet:
            self._console.print(msg)

    def bar(self, current: int, total: int, *, prefix: str = "") -> None:
        if self.quiet or total <= 0:
            return

        if self._progress is None or self._task_total != total:
            self._stop_bar()
            self._progress = RichProgress(
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                console=self._console,
                transient=True,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(prefix.rstrip(), total=total)
            self._task_total = total

        assert self._progress is not None and self._task_id is not None
        self._progress.update(self._task_id, completed=current, description=prefix.rstrip())
        if current >= total:
            self._stop_bar()

    def _stop_bar(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task_id = None
            self._task_total = 0

    def __del__(self) -> None:
        self._stop_bar()
