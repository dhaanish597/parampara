"""Fail on surveillance or biometric features (BUILD_PLAN 27, AGENTS.md)."""

import re
import subprocess
import sys
from pathlib import Path

# Terms prefixed `no_` are licence prohibitions (no_individual_productivity_scoring), not features.
BANNED = re.compile(
    r"(?<!no_individual_)(?<!no_)(?:productivity|idle_time|idle-time|rank_worker|worker_rank"
    r"|face_recognition|facial_recognition|face_match|biometric_id|speed_score"
    r"|worker_leaderboard)",
    re.IGNORECASE,
)
SCANNED_ROOTS = ("apps/", "packages/", "services/", "db/", "contracts/")
SKIPPED = ("node_modules/", ".next/", "tests/test_no_surveillance.py")
SUFFIXES = {".py", ".ts", ".tsx", ".sql", ".json", ".md"}


def candidate_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True, capture_output=True, text=True,
    ).stdout.split("\n")
    return [Path(p) for p in out if p.startswith(SCANNED_ROOTS)
            and Path(p).suffix in SUFFIXES and not any(s in p for s in SKIPPED) and Path(p).exists()]


def main() -> int:
    hits = 0
    for path in candidate_files():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if BANNED.search(line):
                print(f"{path}:{n} banned term: {line.strip()[:80]}")
                hits += 1
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
