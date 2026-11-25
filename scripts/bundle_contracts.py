"""Bundle every file in contracts/schemas into one schema with a $defs entry per file.

Cross-file references (`skill-graph.schema.json#/$defs/X`) become local (`#/$defs/X`) so one
generator run emits one file. Def names must be unique across files; a clash fails the build.
"""

import json
import sys
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parent.parent / "contracts" / "schemas"
ROOT_KEYS = ("$schema", "$id", "$defs")


def rewrite(node: object, titles: dict[str, str]) -> object:
    if isinstance(node, dict):
        out = {k: rewrite(v, titles) for k, v in node.items()}
        ref = out.get("$ref")
        if isinstance(ref, str) and ".schema.json" in ref:
            file, _, frag = ref.partition("#")
            out["$ref"] = f"#{frag}" if frag else f"#/$defs/{titles[file]}"
        return out
    if isinstance(node, list):
        return [rewrite(v, titles) for v in node]
    return node


def bundle() -> dict:
    files = sorted(SCHEMAS.glob("*.schema.json"))
    loaded = {f.name: json.loads(f.read_text()) for f in files}
    titles = {name: s["title"] for name, s in loaded.items()}
    defs: dict[str, object] = {}
    for name, schema in loaded.items():
        body = {k: v for k, v in schema.items() if k not in ROOT_KEYS}
        entries = {**schema.get("$defs", {}), titles[name]: body}
        for key, value in entries.items():
            if key in defs:
                raise SystemExit(f"duplicate contract definition name: {key} (in {name})")
            defs[key] = rewrite(value, titles)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Contracts",
        "type": "object",
        "additionalProperties": False,
        "properties": {t: {"$ref": f"#/$defs/{t}"} for t in sorted(titles.values())},
        "$defs": defs,
    }


if __name__ == "__main__":
    json.dump(bundle(), sys.stdout, indent=2, sort_keys=True)
