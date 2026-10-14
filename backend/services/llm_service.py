"""Provider-agnostic LLM access for the ORQEVA AI Instructor.

No SDK dependency: talks to each provider's REST endpoint with `requests`.
Provider is chosen by LLM_PROVIDER (openai | anthropic | gemini), model by
LLM_MODEL (with a per-provider default). When no key is configured,
`configured()` is False and callers fall back to scripted content.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "gemini": "gemini-1.5-flash",
}


def _clean(value: str | None) -> str:
    v = (value or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'"):
        v = v[1:-1].strip()
    return v


def provider() -> str:
    return _clean(os.getenv("LLM_PROVIDER")) or "openai"


def _api_key(prov: str) -> str:
    if prov == "openai":
        return _clean(os.getenv("OPENAI_API_KEY"))
    if prov == "anthropic":
        return _clean(os.getenv("ANTHROPIC_API_KEY"))
    if prov == "gemini":
        return _clean(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return ""


def model() -> str:
    return _clean(os.getenv("LLM_MODEL")) or _DEFAULT_MODELS.get(provider(), "gpt-4o-mini")


def configured() -> bool:
    return bool(_api_key(provider()))


def status() -> dict[str, Any]:
    prov = provider()
    return {"provider": prov, "model": model(), "configured": configured()}


def _openai(messages, system, temperature, max_tokens, key, mdl) -> str:
    payload = {
        "model": mdl,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"].get("message", "openai_error"))[:200])
    return data["choices"][0]["message"]["content"]


def _anthropic(messages, system, temperature, max_tokens, key, mdl) -> str:
    payload: dict[str, Any] = {
        "model": mdl,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        payload["system"] = system
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    data = r.json()
    if not isinstance(data, dict) or data.get("type") == "error" or "error" in data:
        raise RuntimeError(str(data.get("error", data))[:200])
    return "".join(block.get("text", "") for block in data.get("content", []))


def _gemini(messages, system, temperature, max_tokens, key, mdl) -> str:
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent"
    r = requests.post(url, params={"key": key}, json=payload, timeout=60)
    data = r.json()
    if not isinstance(data, dict) or data.get("error"):
        raise RuntimeError(str(data.get("error", data))[:200])
    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))


def _dispatch(prov, messages, system, temperature, max_tokens, key, mdl) -> str:
    if prov == "openai":
        return _openai(messages, system, temperature, max_tokens, key, mdl)
    if prov == "anthropic":
        return _anthropic(messages, system, temperature, max_tokens, key, mdl)
    if prov == "gemini":
        return _gemini(messages, system, temperature, max_tokens, key, mdl)
    raise RuntimeError(f"unknown_provider:{prov}")


def chat_sync(
    messages: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 700,
) -> str | None:
    """Blocking completion. Returns None when unconfigured or on failure."""
    prov = provider()
    key = _api_key(prov)
    if not key:
        return None
    try:
        return _dispatch(prov, messages, system, temperature, max_tokens, key, model())
    except Exception as e:  # never break the request on a provider hiccup
        logger.warning("LLM call failed (%s): %s", prov, e)
        return None


async def chat(
    messages: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 700,
) -> str | None:
    return await asyncio.to_thread(
        chat_sync, messages, system=system, temperature=temperature, max_tokens=max_tokens
    )
