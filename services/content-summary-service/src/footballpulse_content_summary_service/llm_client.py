from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


class MockLLMClient:
    """Mock LLM client for deterministic testing and offline runs."""

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def generate(self, prompt: str) -> str:
        if "Aggregated News Summary:" in prompt or "news editor" in prompt:
            return "Summary: Recent developments and match updates regarding the team and key players."
        if "Short Description / Headline:" in prompt or "headlines" in prompt:
            return "Key match updates and recent performance overview."
        return "Generated football intelligence summary."


class OpenAILLMClient:
    """OpenAI or compatible provider (e.g. OpenRouter, vLLM, DeepSeek)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"]).strip()


class GeminiLLMClient:
    """Google Gemini API client using standard HTTP."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-1.5-flash",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3},
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(part.get("text", "") for part in parts).strip()


def create_llm_client() -> LLMClient:
    """Factory creating LLMClient based on environment variables."""
    provider = os.getenv("FOOTBALLPULSE_LLM_PROVIDER", "").lower()
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("FOOTBALLPULSE_LLM_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if provider == "gemini" or (not provider and gemini_key):
        return GeminiLLMClient(
            api_key=gemini_key or "",
            model=os.getenv("FOOTBALLPULSE_LLM_MODEL", "gemini-1.5-flash"),
        )
    if provider == "openai" or (not provider and openai_key):
        return OpenAILLMClient(
            api_key=openai_key or "",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("FOOTBALLPULSE_LLM_MODEL", "gpt-4o-mini"),
        )
    return MockLLMClient()
