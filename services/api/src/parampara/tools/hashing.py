"""Deterministic SHA-256 hashing helpers (BUILD_PLAN 20.3, 21.2, 31.4).

Exemplar deterministic tool: pure functions, strict mypy types, zero LLM or I/O calls.
"""

from __future__ import annotations

import hashlib
from typing import Any

from parampara.tools.jcs import canonicalize_bytes


def sha256_bytes(data: bytes) -> str:
    """Return lowercase 64-char hex SHA-256 digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return lowercase 64-char hex SHA-256 digest for UTF-8 encoded text."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_canonical_json(obj: Any) -> str:
    """Return lowercase 64-char hex SHA-256 digest of RFC 8785 canonical JSON."""
    return sha256_bytes(canonicalize_bytes(obj))
