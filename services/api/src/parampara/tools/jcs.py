"""RFC 8785 JSON Canonicalization Scheme (JCS) helper (BUILD_PLAN 20.2 & 21.2)."""

from __future__ import annotations

from typing import Any

import rfc8785


def canonicalize_bytes(data: Any) -> bytes:
    """Return canonical RFC 8785 UTF-8 JSON bytes for any JSON-serializable object."""
    return rfc8785.dumps(data)
