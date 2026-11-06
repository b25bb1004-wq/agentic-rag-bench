"""LLM client for an OpenAI-compatible server (llama-server, vLLM) plus a scripted mock. Owned by the lead."""
from __future__ import annotations
from typing import Callable
import requests


class LLM:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", model: str = "local", timeout: float = 300.0):
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def chat(self, messages: list[dict], max_tokens: int = 256, temperature: float = 0.0, seed: int = 0, stop: list[str] | None = None) -> str:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, "seed": seed,
                # Qwen3 thinking off: the agent protocol needs short, parseable replies
                "chat_template_kwargs": {"enable_thinking": False}}
        if stop:
            body["stop"] = stop
        r = requests.post(f"{self.base_url}/v1/chat/completions", json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""


class MockLLM(LLM):
    """script: list of replies returned in order (last one repeats), or a function(messages)->str."""

    def __init__(self, script: list[str] | Callable[[list[dict]], str]):
        self.script, self.calls = script, []

    def chat(self, messages: list[dict], max_tokens: int = 256, temperature: float = 0.0, seed: int = 0, stop: list[str] | None = None) -> str:
        self.calls.append(messages)
        if callable(self.script):
            return self.script(messages)
        i = min(len(self.calls) - 1, len(self.script) - 1)
        return self.script[i]
