"""OpenRouter LLM client qua OpenAI Python SDK."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from lib.config import (
    openrouter_api_key,
    openrouter_app_name,
    openrouter_base_url,
    openrouter_model,
    openrouter_site_url,
)
from lib.registry import CoinRegistry, filter_allowed_coin_ids
from lib.rules import Mention

_SYSTEM_PROMPT = """You extract cryptocurrency coin mentions from social/news text.
Return ONLY valid JSON with this schema:
{
  "mentions": [
    {"coin_id": "BTC", "evidence": "short quote from text", "confidence": 0.0}
  ]
}
Rules:
- coin_id MUST be one of the allowed coin IDs only.
- Do not invent coins outside the allowed list.
- Include a coin only if the text clearly refers to that asset.
- Ignore generic word "crypto" unless a specific coin is implied.
- confidence is between 0 and 1.
- If no allowed coin is mentioned, return {"mentions": []}.
"""


def _build_user_prompt(*, text: str, registry: CoinRegistry, rules_mentions: list[Mention] | None) -> str:
    rules_block = ""
    if rules_mentions:
        items = [
            f"- {m.coin_id} (evidence: {m.evidence}, method: {m.method})" for m in rules_mentions
        ]
        rules_block = (
            "Rule-based extractor found these candidate mentions. "
            "Confirm, remove false positives, or add missing ones:\n"
            + "\n".join(items)
            + "\n\n"
        )

    return (
        f"Allowed coins:\n{registry.prompt_coin_list()}\n\n"
        f"{rules_block}"
        f"Text:\n{text}\n"
    )


def _parse_llm_json(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _mentions_from_llm_data(data: dict[str, Any], registry: CoinRegistry) -> list[Mention]:
    raw = data.get("mentions")
    if not isinstance(raw, list):
        return []

    out: list[Mention] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        coin_id = str(item.get("coin_id") or "").upper().strip()
        if coin_id not in registry.allowed_ids or coin_id in seen:
            continue
        seen.add(coin_id)
        evidence = str(item.get("evidence") or coin_id).strip()
        conf_raw = item.get("confidence", 0.8)
        try:
            confidence = float(conf_raw)
        except (TypeError, ValueError):
            confidence = 0.8
        out.append(
            Mention(
                coin_id=coin_id,
                evidence=evidence,
                method="llm",
                confidence=max(0.0, min(1.0, confidence)),
            )
        )
    return out


class OpenRouterNER:
    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or openrouter_model()
        self.timeout = timeout

        default_headers: dict[str, str] = {"X-Title": openrouter_app_name()}
        site = openrouter_site_url()
        if site:
            default_headers["HTTP-Referer"] = site

        self._client = OpenAI(
            api_key=api_key or openrouter_api_key(),
            base_url=(base_url or openrouter_base_url()).rstrip("/"),
            timeout=timeout,
            default_headers=default_headers,
        )

    def extract(
        self,
        text: str,
        registry: CoinRegistry,
        *,
        rules_mentions: list[Mention] | None = None,
    ) -> list[Mention]:
        if not text.strip():
            return []

        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        text=text,
                        registry=registry,
                        rules_mentions=rules_mentions,
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        data = _parse_llm_json(content)
        mentions = _mentions_from_llm_data(data, registry)
        allowed = filter_allowed_coin_ids([m.coin_id for m in mentions], registry)
        return [m for m in mentions if m.coin_id in allowed]
