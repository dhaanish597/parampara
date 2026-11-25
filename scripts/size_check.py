"""Fail on source files over 300 lines or functions over 40 lines (AGENTS.md)."""

import ast
import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_LINES = 300
MAX_FUNC_LINES = 40
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".sql"}
EXCLUDED = (
    "packages/contracts/src/generated/",
    "services/api/src/parampara/domain/generated.py",
    "contracts/fixtures/",
    "db/seed/",
    "node_modules/",
    ".next/",
    "spikes/",
    "evals/runs/",
)
TS_FUNC = re.compile(r"^\s*(export\s+)?(async\s+)?function\b|=>\s*\{\s*$")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True, capture_output=True, text=True,
    ).stdout.split("\n")
    return [Path(p) for p in out if p and Path(p).suffix in SOURCE_SUFFIXES
            and not p.startswith(EXCLUDED) and Path(p).exists()]


def py_function_problems(path: Path, text: str) -> list[str]:
    problems = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAX_FUNC_LINES:
                problems.append(f"{path}:{node.lineno} function {node.name} is {length} lines")
    return problems


def ts_function_problems(path: Path, lines: list[str]) -> list[str]:
    problems = []
    for i, line in enumerate(lines):
        if not TS_FUNC.search(line):
            continue
        depth, end = 0, i
        for j in range(i, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            end = j
            if depth <= 0 and j > i or (depth == 0 and "{" in lines[j] and "}" in lines[j]):
                break
        if end - i + 1 > MAX_FUNC_LINES:
            problems.append(f"{path}:{i + 1} function is {end - i + 1} lines")
    return problems


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems = []
    if len(lines) > MAX_FILE_LINES:
        problems.append(f"{path} is {len(lines)} lines (max {MAX_FILE_LINES})")
    if path.suffix == ".py":
        problems += py_function_problems(path, text)
    elif path.suffix in {".ts", ".tsx"}:
        problems += ts_function_problems(path, lines)
    return problems


def main() -> int:
    problems = [p for f in tracked_files() for p in check(f)]
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
