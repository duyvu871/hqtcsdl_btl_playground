"""L2 — SimHash near-duplicate detection.

Phát hiện copy-paste / coordinated spam trong cùng worker session.
khác MongoDB dedup (source, external_id) ở ingest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simhash import Simhash, SimhashIndex


@dataclass
class DedupState:
    """Giữ fingerprint trong lifetime worker — phát hiện copy-paste gần giống."""

    hamming_k: int = 3  # ngưỡng Hamming distance — càng nhỏ càng strict
    fingerprint_bits: int = 64
    _index: SimhashIndex = field(init=False)
    _hashes: list[int] = field(init=False)

    def __post_init__(self) -> None:
        self._index = SimhashIndex([], f=self.fingerprint_bits, k=self.hamming_k)
        self._hashes = []

    def is_duplicate(self, text: str) -> bool:
        """True nếu text gần trùng với entry đã thấy trong session."""
        clean = " ".join(str(text or "").split())
        if not clean:
            return False

        sh = Simhash(clean, f=self.fingerprint_bits)
        if self._index.get_near_dups(sh):
            return True

        hash_value = sh.value
        if hash_value is None:
            return False

        self._index.add(str(len(self._hashes)), sh)
        self._hashes.append(int(hash_value))
        return False
