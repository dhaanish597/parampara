"""Tests for exemplar deterministic hashing tool (BUILD_PLAN 31.4)."""

from __future__ import annotations

from parampara.tools.hashing import sha256_bytes, sha256_canonical_json, sha256_text


def test_sha256_helpers_are_deterministic() -> None:
    assert sha256_bytes(b"parampara") == sha256_text("parampara")
    assert len(sha256_text("parampara")) == 64
    assert sha256_canonical_json({"b": 1, "a": 2}) == sha256_canonical_json({"a": 2, "b": 1})
