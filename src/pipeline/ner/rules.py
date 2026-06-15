"""L1 NER rules — cashtag regex + registry alias + ingest metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.pipeline.ner.registry import CoinRegistry

_CASHTAG_RE = re.compile(r"\$([A-Za-z]{2,10})\b")
_CRYPTO_HINT_RE = re.compile(
    r"(?i)\b(crypto|cryptocurrency|bitcoin|ethereum|blockchain|altcoin|defi|web3)\b"
)


@dataclass(frozen=True)
class Mention:
    coin_id: str
    evidence: str
    method: str = "rules"
    confidence: float = 1.0


@dataclass
class RuleResult:
    mentions: list[Mention] = field(default_factory=list)
    ambiguous: bool = False
    unknown_cashtags: list[str] = field(default_factory=list)
    used_metadata: bool = False


def _event_text(event: dict[str, Any]) -> str:
    return str(event.get("clean_text") or event.get("raw_text") or "").strip()


def _metadata_coin_ids(event: dict[str, Any], registry: CoinRegistry) -> list[str]:
    out: list[str] = []

    related = event.get("related_tickers")
    if isinstance(related, list):
        for item in related:
            sym = str(item).upper().replace("CRYPTO:", "").replace("-USD", "").strip()
            if sym in registry.allowed_ids:
                out.append(sym)

    link_meta = event.get("link_meta")
    if isinstance(link_meta, dict):
        sym = str(link_meta.get("symbol") or "").upper().replace("-USD", "").strip()
        if sym in registry.allowed_ids:
            out.append(sym)

    return out


def extract_rules(event: dict[str, Any], registry: CoinRegistry) -> RuleResult:
    text = _event_text(event)
    result = RuleResult()
    seen: set[str] = set()

    for coin_id in _metadata_coin_ids(event, registry):
        if coin_id not in seen:
            seen.add(coin_id)
            result.mentions.append(
                Mention(coin_id=coin_id, evidence=f"metadata:{coin_id}", method="metadata")
            )
            result.used_metadata = True

    for match in _CASHTAG_RE.finditer(text):
        symbol = match.group(1)
        coin_id = registry.resolve_cashtag(symbol)
        if coin_id and coin_id not in seen:
            seen.add(coin_id)
            result.mentions.append(
                Mention(coin_id=coin_id, evidence=match.group(0), method="cashtag")
            )
        elif not coin_id:
            result.unknown_cashtags.append(f"${symbol.upper()}")

    lowered = text.lower()
    for coin in registry.coins:
        if coin.coin_id in seen:
            continue
        for alias in coin.aliases:
            if len(alias) <= 2 and alias not in ("btc", "eth", "sol", "bnb", "xrp", "ada", "dot"):
                continue
            pattern = rf"\b{re.escape(alias)}\b"
            m = re.search(pattern, lowered, flags=re.IGNORECASE)
            if m:
                seen.add(coin.coin_id)
                result.mentions.append(
                    Mention(
                        coin_id=coin.coin_id,
                        evidence=text[m.start() : m.end()],
                        method="keyword",
                        confidence=0.85 if len(alias) <= 4 else 0.9,
                    )
                )
                break

    if result.unknown_cashtags:
        result.ambiguous = True
    if not result.mentions and _CRYPTO_HINT_RE.search(text):
        result.ambiguous = True
    if len(result.mentions) > 4:
        result.ambiguous = True

    return result


def looks_crypto_related(text: str) -> bool:
    return bool(_CRYPTO_HINT_RE.search(text) or _CASHTAG_RE.search(text))
