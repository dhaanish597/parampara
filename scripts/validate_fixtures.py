"""Validate every contracts/fixtures/*.json against its schema (matched by filename prefix)."""

import json
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).parent))
from bundle_contracts import SCHEMAS, bundle  # noqa: E402

FIXTURES = SCHEMAS.parent / "fixtures"


def schema_for(stem: str, titles: dict[str, str]) -> str | None:
    matches = [n for n in titles if stem == n or stem.startswith(n + ".")]
    return max(matches, key=len, default=None)


def main() -> int:
    defs = bundle()["$defs"]
    titles = {
        p.name.removesuffix(".schema.json"): json.loads(p.read_text())["title"]
        for p in SCHEMAS.glob("*.schema.json")
    }
    failures = 0
    covered: set[str] = set()
    for fixture in sorted(FIXTURES.glob("*.json")):
        name = schema_for(fixture.stem, titles)
        if name is None:
            print(f"{fixture.name}: no matching schema")
            failures += 1
            continue
        covered.add(name)
        schema = {"$ref": f"#/$defs/{titles[name]}", "$defs": defs}
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(json.loads(fixture.read_text())))
        for err in errors[:5]:
            print(f"{fixture.name}: {'/'.join(map(str, err.path))}: {err.message[:120]}")
        failures += bool(errors)
    for missing in sorted(set(titles) - covered):
        print(f"missing fixture for schema: {missing}")
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
