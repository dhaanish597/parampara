"""SHA-256 Merkle evidence root and evidence query (BUILD_PLAN 20.3)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MERKLE_ALGORITHM = "sha256-merkle-v1"

EVIDENCE_QUERY_SQL = """
SELECT hash_hex FROM (
    SELECT 0 AS bucket, c.created_at, c.sha256 AS hash_hex
    FROM sessions s
    JOIN clips c ON c.id = s.clip_id
    WHERE s.trainee_user_id = %(user_id)s
      AND s.skill_version_id = %(skill_version_id)s
      AND s.status = 'completed'
      AND coalesce((s.summary->>'clean_run')::boolean, false) = true
      AND c.sha256 IS NOT NULL
    UNION ALL
    SELECT 1 AS bucket, e.created_at, e.frame_sha256 AS hash_hex
    FROM sessions s
    JOIN step_events e ON e.session_id = s.id
    WHERE s.trainee_user_id = %(user_id)s
      AND s.skill_version_id = %(skill_version_id)s
      AND s.status = 'completed'
      AND coalesce((s.summary->>'clean_run')::boolean, false) = true
      AND e.type = 'vlm_key'
      AND e.frame_sha256 IS NOT NULL
) evidence
ORDER BY bucket ASC, created_at ASC, hash_hex ASC
"""


def merkle_root_hex(leaf_hashes_hex: Sequence[str]) -> str:
    """Compute sha256-merkle-v1 root from lowercase 64-char hex SHA-256 leaf digests."""
    if not leaf_hashes_hex:
        raise ValueError("Evidence leaf list cannot be empty")
    level: list[bytes] = []
    for h in leaf_hashes_hex:
        norm = h.lower()
        if not HEX64_RE.match(norm):
            raise ValueError(f"Invalid SHA-256 hex digest: {h}")
        level.append(bytes.fromhex(norm))

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[bytes] = []
        for idx in range(0, len(level), 2):
            next_level.append(hashlib.sha256(level[idx] + level[idx + 1]).digest())
        level = next_level
    return level[0].hex()
