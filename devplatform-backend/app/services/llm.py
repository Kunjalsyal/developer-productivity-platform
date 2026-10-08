from __future__ import annotations

import json
import re
from typing import Protocol

from ..config import get_settings


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


class AnthropicLLM:
    def __init__(self, api_key: str | None, model: str):
        import anthropic

        self.client, self.model = anthropic.Anthropic(api_key=api_key), model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        r = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                        messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if b.type == "text")


class OpenAILLM:
    def __init__(self, api_key: str | None, model: str, base_url: str | None = None):
        from openai import OpenAI

        self.client, self.model = OpenAI(api_key=api_key, base_url=base_url), model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        r = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""


class FakeLLM:
    """Deterministic, extractive stand-in for tests and offline demos (no network)."""

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        if "TASK: PR_SUMMARY" in user:
            m = re.search(r"Title: (.+)", user)
            return json.dumps({"summary": f"This pull request: {m.group(1) if m else 'changes code'}.",
                               "why": "", "review_notes": []})
        m = re.search(r"\[1\] (.+?):(\d+)-(\d+) \((\w+) (.*?)\)", user)
        if not m:
            return json.dumps({"answer": "", "citations": [], "sufficient": False})
        path, _, _, _, name = m.groups()
        return json.dumps({"answer": f"The relevant code is `{name}` in {path} [1].",
                           "citations": [1], "sufficient": True})


def get_llm() -> LLMClient:
    s = get_settings()
    if s.llm_provider == "anthropic":
        return AnthropicLLM(s.anthropic_api_key, s.llm_model or "claude-sonnet-5-5")
    if s.llm_provider == "openai":
        return OpenAILLM(s.openai_api_key, s.llm_model or "gpt-4o-mini", s.openai_base_url)
    if s.llm_provider == "groq":  # free tier, OpenAI-compatible API
        return OpenAILLM(s.groq_api_key, s.llm_model or "llama-3.3-70b-versatile",
                         s.openai_base_url or "https://api.groq.com/openai/v1")
    if s.llm_provider == "ollama":  # fully local, no key
        return OpenAILLM("ollama", s.llm_model or "llama3.2",
                         s.openai_base_url or "http://host.docker.internal:11434/v1")
    if s.llm_provider == "fake":
        return FakeLLM()
    raise ValueError(f"unknown LLM_PROVIDER: {s.llm_provider}")
