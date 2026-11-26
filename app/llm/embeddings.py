"""Turn text into vectors so the knowledge base can search by meaning.

Same rule as the chat models: only this package talks to a provider. Offline mode uses a
deterministic word-hashing embedder, so tests and demos are free and repeatable. It matches
shared words rather than meaning, which is enough to test the plumbing, not to judge quality.
"""
import hashlib
import math
import os
import re
from typing import Protocol

from app.llm.client import LIVE_MODES, LLMError

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
OFFLINE_DIM = 256
_WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalise(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class OfflineEmbedder:
    model = "offline:hash-256"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            v = [0.0] * OFFLINE_DIM
            for word in _WORD.findall(text.lower()):
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                v[h % OFFLINE_DIM] += 1.0
            out.append(_normalise(v))
        return out


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = EMBED_MODEL):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, max_retries=3)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            res = self._client.embeddings.create(model=self.model, input=texts)
        except Exception as err:  # provider errors become one readable type
            raise LLMError(f"embedding failed: {err}") from err
        return [d.embedding for d in res.data]


def get_embedder() -> Embedder:
    if os.getenv("LLM_MODE", "offline") in LIVE_MODES:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMError("embeddings need OPENAI_API_KEY")
        return OpenAIEmbedder(key)
    return OfflineEmbedder()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
