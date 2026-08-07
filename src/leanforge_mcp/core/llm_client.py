"""
Multi-tier LLM client.
Supports Ollama (local), OpenAI-compatible (DeepSeek), Anthropic.
Handles per-subagent tier escalation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import anthropic
from openai import AsyncOpenAI

from leanforge_mcp.core.config import LLMConfig, LLMTierConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMClient:
    config: LLMConfig
    start_tier: int = 1
    escalate_to_tier2_after: int = 20
    escalate_to_tier3_after: int = 60
    # _current_tier is internal state, not an init argument.
    # field(init=False) keeps it out of __init__ and repr comparisons.
    _current_tier: int = field(init=False)

    def __post_init__(self):
        self._current_tier = self.start_tier

    @property
    def current_model(self) -> str:
        return self._tier_config.model

    @property
    def _tier_config(self) -> LLMTierConfig:
        if self._current_tier == 1:
            return self.config.tier1
        if self._current_tier == 2:
            return self.config.tier2
        return self.config.tier3

    async def maybe_escalate(self, turn: int) -> None:
        if self._current_tier == 1 and turn >= self.escalate_to_tier2_after:
            logger.info("Escalating to tier 2 at turn %d (model: %s)", turn, self.config.tier2.model)
            self._current_tier = 2
        elif self._current_tier == 2 and turn >= self.escalate_to_tier3_after:
            logger.info("Escalating to tier 3 at turn %d (model: %s)", turn, self.config.tier3.model)
            self._current_tier = 3

    async def complete(self, system: str, user: str) -> str:
        cfg = self._tier_config
        if cfg.provider in ("ollama", "openai_compat"):
            return await self._complete_openai_compat(cfg, system, user)
        if cfg.provider == "anthropic":
            return await self._complete_anthropic(cfg, system, user)
        raise ValueError(f"Unknown LLM provider: {cfg.provider!r}")

    async def _complete_openai_compat(self, cfg: LLMTierConfig, system: str, user: str) -> str:
        api_key = "ollama"
        if cfg.api_key_env:
            api_key = os.environ.get(cfg.api_key_env, "")
            if not api_key:
                raise ValueError(f"API key environment variable {cfg.api_key_env!r} is not set.")
        client = AsyncOpenAI(api_key=api_key, base_url=cfg.base_url)
        response = await client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""

    async def _complete_anthropic(self, cfg: LLMTierConfig, system: str, user: str) -> str:
        api_key = os.environ.get(cfg.api_key_env, "")
        if not api_key:
            raise ValueError(f"Anthropic API key not set. Set environment variable: {cfg.api_key_env}")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if message.content and hasattr(message.content[0], "text"):
            return message.content[0].text
        return ""
