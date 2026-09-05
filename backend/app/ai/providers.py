"""Provider adapters. Every external request reserves quota before sending."""
import hashlib
import json
import math
from typing import Protocol, Callable, Awaitable

import httpx

Charge = Callable[[str], Awaitable[None]]


class Provider(Protocol):
    async def complete(self, messages: list[dict], kind: str = "chat") -> dict: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def vision(self, prompt: str, images: list[dict]) -> dict: ...


def setting(settings, key, default=None):
    if isinstance(settings, dict):
        return settings.get(key, settings.get(key.lower(), default))
    return getattr(settings, key, getattr(settings, key.lower(), default))


class FakeProvider:
    """Explicit deterministic test provider: no live knowledge or model inference."""
    def __init__(self, dimension=32):
        self.dimension = dimension

    async def complete(self, messages, kind="chat"):
        return {}

    async def embed(self, texts):
        result = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in text.casefold():
                digest = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % self.dimension] += 1
            norm = math.sqrt(sum(x*x for x in vector)) or 1
            result.append([x/norm for x in vector])
        return result

    async def vision(self, prompt, images):
        return {"text": "", "pages": len(images), "provider": "fake"}


class CompatibleProvider:
    def __init__(self, settings, charge=None, transport=None):
        self.settings, self.charge, self.transport = settings, charge, transport

    async def _post(self, prefix, path, body, kind):
        if self.charge is None:
            raise RuntimeError("External AI requires a quota reservation callback")
        await self.charge(kind)
        base = setting(self.settings, prefix + "_BASE_URL", "").rstrip("/")
        key = setting(self.settings, prefix + "_API_KEY", "")
        if not base or not key:
            raise ValueError("AI endpoint and key are required")
        async with httpx.AsyncClient(timeout=float(setting(self.settings, "MODEL_TIMEOUT_SECONDS", 30)), transport=self.transport) as client:
            response = await client.post(base + path, headers={"Authorization": "Bearer " + key}, json=body)
            response.raise_for_status()
            if len(response.content) > 4_000_000:
                raise ValueError("Provider response exceeds size limit")
            return response.json()

    async def complete(self, messages, kind="chat"):
        data = await self._post("CHAT", "/chat/completions", {
            "model": setting(self.settings, "CHAT_MODEL"), "messages": messages,
            "max_tokens": int(setting(self.settings, "MAX_OUTPUT_TOKENS", 2000)),
            "response_format": {"type": "json_object"}, "temperature": 0.2,
        }, kind)
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object")
        return result

    async def embed(self, texts):
        data = await self._post("EMBEDDING", "/embeddings", {
            "model": setting(self.settings, "EMBEDDING_MODEL"), "input": texts,
        }, "embedding")
        rows = sorted(data["data"], key=lambda row: row["index"])
        if [row["index"] for row in rows] != list(range(len(texts))):
            raise ValueError("Embedding response indices mismatch")
        return [row["embedding"] for row in rows]

    async def vision(self, prompt, images):
        content = [{"type": "text", "text": prompt}]
        content.extend({"type": "image_url", "image_url": {"url": image["data_uri"]}} for image in images)
        data = await self._post("CHAT", "/chat/completions", {
            "model": setting(self.settings, "VISION_MODEL", setting(self.settings, "CHAT_MODEL")),
            "messages": [{"role": "user", "content": content}],
            "max_tokens": int(setting(self.settings, "MAX_OUTPUT_TOKENS", 2000)),
            "response_format": {"type": "json_object"}, "temperature": 0.1,
        }, "vision")
        result = json.loads(data["choices"][0]["message"]["content"])
        if not isinstance(result, dict) or not isinstance(result.get("text", ""), str):
            raise ValueError("Expected vision JSON object with text")
        return result
