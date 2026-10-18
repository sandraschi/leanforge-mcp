"""LLM provider registry + backend chat proxy.

The webapp Chat page must NEVER call providers directly from the browser
(API keys would leak, localhost URLs break on LAN/Tailscale tabs). Every
chat completion goes through POST /api/llm/chat (JSON) or
POST /api/llm/chat/stream (SSE, OpenAI-style chunks) here.
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from leanforge_mcp.core.llm_client import LLMClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["llm"])


class ChatMessage(BaseModel):
    role: str = Field(description="'system', 'user' or 'assistant'.")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    system: str = Field(default="", description="System preprompt (skill + personality, composed client-side).")
    tier: int = Field(default=1, ge=1, le=3, description="1=local Ollama, 2=DeepSeek API, 3=Anthropic.")
    stream: bool = Field(default=False, description="Only honoured by /chat/stream.")


def _provider_info(request: Request) -> list[dict]:
    """Local reachability is probed live; cloud shows configured flags only (never keys)."""
    config = request.app.state.config
    return [
        {
            "id": "local",
            "label": "Local (Ollama)",
            "tier": 1,
            "model": config.llm.tier1.model,
            "base_url": config.llm.tier1.base_url,
            "free": True,
        },
        {
            "id": "deepseek",
            "label": "DeepSeek API",
            "tier": 2,
            "model": config.llm.tier2.model,
            "configured": bool(config.llm.tier2.api_key_env and os.environ.get(config.llm.tier2.api_key_env)),
            "free": False,
        },
        {
            "id": "anthropic",
            "label": "Anthropic",
            "tier": 3,
            "model": config.llm.tier3.model,
            "configured": bool(config.llm.tier3.api_key_env and os.environ.get(config.llm.tier3.api_key_env)),
            "free": False,
        },
    ]


async def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except httpx.HTTPError:
        return False


@router.get("/providers")
async def list_providers(request: Request):
    """Provider registry: local detected flags + cloud configured flags (never key bytes)."""
    config = request.app.state.config
    ollama_root = config.llm.tier1.base_url.rsplit("/v1", 1)[0]
    local_ok = await _probe(f"{ollama_root}/api/tags")
    lmstudio_ok = await _probe("http://localhost:1234/v1/models")
    providers = _provider_info(request)
    providers[0]["detected"] = local_ok
    providers.append(
        {
            "id": "lmstudio",
            "label": "LM Studio",
            "tier": 1,
            "model": "(any loaded model)",
            "base_url": "http://localhost:1234/v1",
            "free": True,
            "detected": lmstudio_ok,
        }
    )
    return {"providers": providers}


@router.get("/discover")
async def discover(request: Request):
    """Subset of /providers for the Chat status indicator: local presence only."""
    config = request.app.state.config
    ollama_root = config.llm.tier1.base_url.rsplit("/v1", 1)[0]
    return {
        "ollama": await _probe(f"{ollama_root}/api/tags"),
        "lm_studio": await _probe("http://localhost:1234/v1/models"),
    }


@router.get("/models")
async def list_models(request: Request):
    """Model list per provider: live when reachable, curated fallback otherwise."""
    config = request.app.state.config
    ollama_root = config.llm.tier1.base_url.rsplit("/v1", 1)[0]
    models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_root}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
    except httpx.HTTPError:
        logger.debug("Ollama not reachable for model list; using fallback")
    if not models:
        models = [config.llm.tier1.model, config.llm.tier2.model, config.llm.tier3.model]
    return {"models": models, "live": bool(models) and models != [config.llm.tier1.model]}


@router.get("/onboarding")
async def onboarding(request: Request):
    """Fresh-install starter facts + recommended path for the under-hero cue."""
    config = request.app.state.config
    ollama_root = config.llm.tier1.base_url.rsplit("/v1", 1)[0]
    ollama_ok = await _probe(f"{ollama_root}/api/tags")
    facts = [
        "Lean 4 compiles every proof -- a sorry-free compile IS correctness.",
        f"Tier-1 proof search runs locally on {config.llm.tier1.model} (free).",
        "Tier-2/3 escalate to DeepSeek / Anthropic APIs when agents stall.",
    ]
    recommended = "validate_lean" if ollama_ok else "install_ollama"
    return {"facts": facts, "recommended_path": recommended, "ollama_detected": ollama_ok}


def _split_history(messages: list[ChatMessage]) -> tuple[str, str]:
    """Collapse history into (system_extra, user_block) for single-turn complete()."""
    turns = []
    for m in messages:
        if m.role == "system":
            continue
        turns.append(f"{m.role.upper()}: {m.content}")
    history = "\n\n".join(turns[:-1])
    last = messages[-1].content if messages and messages[-1].role == "user" else ""
    user_block = f"Conversation so far:\n{history}\n\nLatest user message:\n{last}" if history else last
    return user_block


def _client_for(request: Request, tier: int) -> LLMClient:
    config = request.app.state.config
    return LLMClient(config=config.llm, start_tier=tier)


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Backend chat proxy (JSON). Keys never leave the server."""
    try:
        client = _client_for(request, body.tier)
        reply = await client.complete(system=body.system, user=_split_history(body.messages))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("LLM chat failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}") from exc
    return {"reply": reply, "tier": body.tier, "model": client.current_model}


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """Backend chat proxy (SSE, OpenAI-style chunks). Keys never leave the server."""

    async def event_generator():
        try:
            client = _client_for(request, body.tier)
            cfg = client._tier_config
            if cfg.provider in ("ollama", "openai_compat"):
                api_key = os.environ.get(cfg.api_key_env, "") if cfg.api_key_env else "ollama"
                oai = AsyncOpenAI(api_key=api_key or "ollama", base_url=cfg.base_url)
                msgs: list[dict] = []
                if body.system:
                    msgs.append({"role": "system", "content": body.system})
                for m in body.messages:
                    if m.role in ("user", "assistant"):
                        msgs.append({"role": m.role, "content": m.content})
                stream = await oai.chat.completions.create(
                    model=cfg.model,
                    messages=msgs,  # type: ignore[arg-type]
                    max_tokens=cfg.max_tokens,
                    temperature=cfg.temperature,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield f"data: {json.dumps({'choices': [{'delta': {'content': delta}}]})}\n\n"
                yield "data: [DONE]\n\n"
            else:
                reply = await client.complete(system=body.system, user=_split_history(body.messages))
                yield f"data: {json.dumps({'choices': [{'delta': {'content': reply}}]})}\n\n"
                yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.warning("LLM stream failed: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
