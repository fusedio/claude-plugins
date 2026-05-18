#!/usr/bin/env python3
"""Regenerate fused-plugin/skills/json-ui-schemas/reference.md from the live CLI."""

import json
import subprocess
import sys
from pathlib import Path

REFERENCE_PATH = Path(__file__).parent.parent / "fused-plugin/skills/json-ui-schemas/reference.md"


def main():
    result = subprocess.run(
        ["fused", "json-ui", "schemas"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)
    components = sorted(data["components"], key=lambda c: c["type"])

    lines = ["# JSON UI component schemas"]
    for comp in components:
        schema = comp.get("propsSchema", {})
        schema.pop("$schema", None)

        lines.append(f"\n## {comp['type']}\n")
        lines.append(comp.get("description", ""))
        lines.append("\n~~~json")
        lines.append(json.dumps(schema, indent=2))
        lines.append("~~~")

    REFERENCE_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(components)} components to {REFERENCE_PATH}")


if __name__ == "__main__":
    main()
