"""L2 — SimHash near-duplicate detection."""

from __future__ import annotations

from dataclasses import dataclass

from simhash import Simhash, SimhashIndex


@dataclass
class DedupState:
    """Giữ fingerprint trong một batch run."""

    hamming_k: int = 3
    fingerprint_bits: int = 64
    _index: SimhashIndex | None = None
    _hashes: list[int] | None = None

    def __post_init__(self) -> None:
        self._index = SimhashIndex([], f=self.fingerprint_bits, k=self.hamming_k)
        self._hashes = []

    def is_duplicate(self, text: str) -> bool:
        assert self._index is not None and self._hashes is not None
        clean = " ".join(str(text or "").split())
        if not clean:
            return False

        sh = Simhash(clean, f=self.fingerprint_bits)
        dupes = self._index.get_near_dups(sh)
        if dupes:
            return True

        self._index.add(str(len(self._hashes)), sh)
        self._hashes.append(sh.value)
        return False
