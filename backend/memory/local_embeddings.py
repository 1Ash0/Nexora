import hashlib
from typing import List


class LocalHashEmbeddings:
    """Lightweight deterministic embeddings without external model downloads."""

    def __init__(self, dim: int = 1536):
        self.dim = dim

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            sign = 1.0 if (h[4] % 2 == 0) else -1.0
            vec[idx] += sign

        norm = sum(v * v for v in vec) ** 0.5
        if norm <= 1e-12:
            return vec
        return [v / norm for v in vec]
