"""Deterministic local embedding — no cloud SDK (CLAUDE.md rule 6).

A hashing bag-of-tokens embedding: each token is hashed into one of
EMBEDDING_DIM buckets, counts are accumulated and L2-normalised. Fully
offline and reproducible. It is deliberately not a semantic model — honest
for a synthetic demo, and enough to exercise the vector half of hybrid
fusion. The same function embeds both stored documents and query text.
"""

import hashlib
import math
import re

EMBEDDING_DIM = 64

_TOKEN = re.compile(r"[a-z0-9]+")


def _bucket(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % EMBEDDING_DIM


def embed(text: str) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    for token in _TOKEN.findall(text.lower()):
        vec[_bucket(token)] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def to_pgvector(vec: list[float]) -> str:
    """pgvector text literal, e.g. '[0.1,0.2,...]', cast to ::vector in SQL —
    avoids a numpy dependency."""
    return "[" + ",".join(repr(x) for x in vec) + "]"
