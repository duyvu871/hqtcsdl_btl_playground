"""NER hybrid pipeline — rules → LLM fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.pipeline.ner.llm import OpenRouterNER
from src.pipeline.ner.registry import CoinRegistry
from src.pipeline.ner.rules import Mention, RuleResult, extract_rules, looks_crypto_related


class NerMode(str, Enum):
    HYBRID = "hybrid"
    VALIDATOR = "validator"
    FULL = "full"

    @classmethod
    def parse(cls, value: str) -> NerMode:
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"Mode không hợp lệ: {value!r}. Chọn: hybrid | validator | full"
            ) from exc


@dataclass
class NerOutcome:
    mentions: list[Mention]
    mode: str
    used_llm: bool
    rule_result: RuleResult | None = None
    llm_error: str | None = None
    notes: str = ""


@dataclass
class NerStats:
    total: int = 0
    with_mentions: int = 0
    without_mentions: int = 0
    fanout_records: int = 0
    llm_calls: int = 0
    llm_errors: int = 0
    by_method: dict[str, int] = field(default_factory=dict)

    def record(self, outcome: NerOutcome, *, fanout_count: int) -> None:
        self.total += 1
        if outcome.mentions:
            self.with_mentions += 1
        else:
            self.without_mentions += 1
        self.fanout_records += fanout_count
        if outcome.used_llm:
            self.llm_calls += 1
        if outcome.llm_error:
            self.llm_errors += 1
        for m in outcome.mentions:
            key = m.method
            self.by_method[key] = self.by_method.get(key, 0) + 1


def _should_call_llm_hybrid(rule_result: RuleResult, text: str) -> bool:
    words = len(text.split())
    if words <= 20 and not rule_result.ambiguous and rule_result.mentions:
        return False
    if rule_result.mentions:
        return rule_result.ambiguous
    return rule_result.ambiguous or looks_crypto_related(text)


def map_event(
    event: dict[str, Any],
    *,
    mode: NerMode,
    registry: CoinRegistry,
    llm: OpenRouterNER | None,
) -> NerOutcome:
    text = str(event.get("clean_text") or event.get("raw_text") or "").strip()
    rule_result = extract_rules(event, registry)

    if mode == NerMode.FULL:
        if llm is None:
            raise ValueError("Mode full cần OpenRouter LLM.")
        try:
            mentions = llm.extract(text, registry)
            return NerOutcome(
                mentions=mentions,
                mode=mode.value,
                used_llm=True,
                rule_result=rule_result,
                notes="full_llm",
            )
        except Exception as exc:
            return NerOutcome(
                mentions=[],
                mode=mode.value,
                used_llm=True,
                rule_result=rule_result,
                llm_error=str(exc),
                notes="full_llm_error",
            )

    if mode == NerMode.HYBRID:
        if llm is not None and _should_call_llm_hybrid(rule_result, text):
            try:
                llm_mentions = llm.extract(text, registry, rules_mentions=rule_result.mentions)
                if llm_mentions:
                    return NerOutcome(
                        mentions=llm_mentions,
                        mode=mode.value,
                        used_llm=True,
                        rule_result=rule_result,
                        notes="hybrid_llm_fallback",
                    )
                return NerOutcome(
                    mentions=rule_result.mentions,
                    mode=mode.value,
                    used_llm=True,
                    rule_result=rule_result,
                    notes="hybrid_llm_empty",
                )
            except Exception as exc:
                if rule_result.mentions:
                    return NerOutcome(
                        mentions=rule_result.mentions,
                        mode=mode.value,
                        used_llm=True,
                        rule_result=rule_result,
                        llm_error=str(exc),
                        notes="hybrid_llm_error_fallback_rules",
                    )
                return NerOutcome(
                    mentions=[],
                    mode=mode.value,
                    used_llm=True,
                    rule_result=rule_result,
                    llm_error=str(exc),
                    notes="hybrid_llm_error",
                )

        return NerOutcome(
            mentions=rule_result.mentions,
            mode=mode.value,
            used_llm=False,
            rule_result=rule_result,
            notes="hybrid_rules_only",
        )

    if llm is None:
        raise ValueError("Mode validator cần OpenRouter LLM.")
    try:
        llm_mentions = llm.extract(text, registry, rules_mentions=rule_result.mentions)
        if llm_mentions:
            mentions = llm_mentions
            notes = "validator_llm_final"
        elif rule_result.mentions:
            mentions = rule_result.mentions
            notes = "validator_rules_kept"
        else:
            mentions = []
            notes = "validator_empty"
        return NerOutcome(
            mentions=mentions,
            mode=mode.value,
            used_llm=True,
            rule_result=rule_result,
            notes=notes,
        )
    except Exception as exc:
        return NerOutcome(
            mentions=rule_result.mentions,
            mode=mode.value,
            used_llm=True,
            rule_result=rule_result,
            llm_error=str(exc),
            notes="validator_llm_error_fallback_rules",
        )
