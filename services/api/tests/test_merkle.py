"""Tests for SHA-256 Merkle evidence root tool (BUILD_PLAN 20.3)."""

from __future__ import annotations

import hashlib

import pytest

from parampara.tools.merkle import EVIDENCE_QUERY_SQL, merkle_root_hex


def _h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _parent(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hexdigest()


def test_merkle_empty_raises() -> None:
    with pytest.raises(ValueError):
        merkle_root_hex([])


def test_merkle_single_leaf_returns_leaf() -> None:
    leaf = _h("clip1")
    assert merkle_root_hex([leaf]) == leaf


def test_merkle_two_leaves() -> None:
    a, b = _h("a"), _h("b")
    assert merkle_root_hex([a, b]) == _parent(a, b)


def test_merkle_three_leaves_duplicates_last() -> None:
    a, b, c = _h("a"), _h("b"), _h("c")
    expected = _parent(_parent(a, b), _parent(c, c))
    assert merkle_root_hex([a, b, c]) == expected


def test_merkle_eight_leaves() -> None:
    leaves = [_h(f"item-{i}") for i in range(8)]
    l1 = [_parent(leaves[i], leaves[i + 1]) for i in range(0, 8, 2)]
    l2 = [_parent(l1[i], l1[i + 1]) for i in range(0, 4, 2)]
    assert merkle_root_hex(leaves) == _parent(l2[0], l2[1])


def test_merkle_rejects_invalid_hex_leaf() -> None:
    with pytest.raises(ValueError):
        merkle_root_hex(["not-a-sha256"])


def test_evidence_query_orders_clips_then_frames_by_created_at() -> None:
    assert "clips" in EVIDENCE_QUERY_SQL
    assert "step_events" in EVIDENCE_QUERY_SQL
    assert "ORDER BY" in EVIDENCE_QUERY_SQL.upper()
