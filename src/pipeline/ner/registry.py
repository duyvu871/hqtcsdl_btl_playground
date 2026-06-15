"""Coin registry — Top 10 MVP alias → coin_id."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.common.config import settings


@dataclass(frozen=True)
class CoinEntry:
    coin_id: str
    name: str
    aliases: tuple[str, ...]


@dataclass
class CoinRegistry:
    coins: tuple[CoinEntry, ...]
    _allowed_ids: frozenset[str]
    _alias_to_id: dict[str, str]
    _cashtag_to_id: dict[str, str]

    @classmethod
    def load(cls, path: Path | None = None) -> CoinRegistry:
        registry_path = path or settings.coin_registry_path
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        coins: list[CoinEntry] = []
        for item in raw.get("coins", []):
            coin_id = str(item.get("coin_id", "")).upper().strip()
            if not coin_id:
                continue
            name = str(item.get("name") or coin_id).strip()
            aliases = tuple(
                sorted(
                    {
                        coin_id.lower(),
                        name.lower(),
                        *(str(a).lower().strip() for a in item.get("aliases") or [] if a),
                    }
                )
            )
            coins.append(CoinEntry(coin_id=coin_id, name=name, aliases=aliases))

        allowed = frozenset(c.coin_id for c in coins)
        alias_map: dict[str, str] = {}
        cashtag_map: dict[str, str] = {}
        for coin in coins:
            cashtag_map[coin.coin_id] = coin.coin_id
            for alias in coin.aliases:
                alias_map[alias] = coin.coin_id
            alias_map[coin.name.lower()] = coin.coin_id

        return cls(
            coins=tuple(coins),
            _allowed_ids=allowed,
            _alias_to_id=alias_map,
            _cashtag_to_id=cashtag_map,
        )

    @property
    def allowed_ids(self) -> frozenset[str]:
        return self._allowed_ids

    def resolve_cashtag(self, symbol: str) -> str | None:
        key = symbol.upper().strip().lstrip("$")
        if key in self._allowed_ids:
            return key
        return None

    def resolve_alias(self, token: str) -> str | None:
        key = token.lower().strip()
        coin_id = self._alias_to_id.get(key)
        if coin_id in self._allowed_ids:
            return coin_id
        return None

    def prompt_coin_list(self) -> str:
        lines = [f"- {c.coin_id}: {c.name} (aliases: {', '.join(c.aliases[:5])})" for c in self.coins]
        return "\n".join(lines)


def filter_allowed_coin_ids(coin_ids: list[str], registry: CoinRegistry) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in coin_ids:
        cid = str(raw or "").upper().strip()
        if cid in registry.allowed_ids and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out
