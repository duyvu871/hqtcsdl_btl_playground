"""Prepare HuggingFace crypto tweet dataset for FastText supervised training."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from datasets import Dataset, load_dataset

DATASET_ID = "sandiumenge/bitcoin-tweets-spam-emotion-sentiment"
SPAM_LABELS = {"spam", "bot"}
HUMAN_LABEL = "human"


def normalize_text(text: str) -> str:
    """Collapse whitespace; strip newlines for single-line FastText format."""
    if not text:
        return ""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_label(raw: str) -> str:
    """Map dataset label to binary FastText label."""
    raw = (raw or "").strip().lower()
    if raw in SPAM_LABELS:
        return "spam"
    if raw == HUMAN_LABEL:
        return "human"
    return "spam"


def to_fasttext_line(label: str, text: str) -> str | None:
    text = normalize_text(text)
    if not text:
        return None
    return f"__label__{label} {text}"


def load_crypto_spam_dataset() -> dict[str, Dataset]:
    return load_dataset(DATASET_ID)


def export_split(dataset: Dataset, out_path: Path) -> int:
    """Write split to FastText format; return number of lines written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for row in dataset:
            label = map_label(str(row.get("spam", "")))
            line = to_fasttext_line(label, str(row.get("text", "")))
            if line:
                f.write(line + "\n")
                count += 1
    return count


def export_all(data_dir: Path) -> dict[str, int]:
    ds = load_crypto_spam_dataset()
    stats = {}
    for split in ("train", "validation", "test"):
        if split in ds:
            stats[split] = export_split(ds[split], data_dir / f"{split}.txt")
    return stats


def sample_lines(path: Path, n: int = 3) -> list[str]:
    lines: list[str] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            lines.append(line.rstrip())
    return lines
