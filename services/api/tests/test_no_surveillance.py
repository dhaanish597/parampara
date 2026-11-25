"""No-surveillance guardrail test (BUILD_PLAN 27)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BANNED = re.compile(r"(?<!no_individual_)(?<!no_)(?:productivity|idle_time|rank_worker)", re.I)


def test_no_surveillance_terms_in_routes_or_views() -> None:
    targets = [
        *(ROOT / "services" / "api" / "src" / "parampara" / "api" / "routes").glob("*.py"),
        *(ROOT / "db" / "migrations").glob("*.sql"),
    ]
    assert targets, "Expected route and migration files to scan"
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert not BANNED.search(text), f"Banned surveillance term in {path}"
