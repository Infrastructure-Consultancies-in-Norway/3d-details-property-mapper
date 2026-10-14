"""Writes ifc-files/output/manifest.json, the model list consumed by the SNACKS IFC viewer website.

Run from the repository root: python scripts/generate_ifc_manifest.py
"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ifc-files" / "output"


def main() -> None:
    models = [
        {"fileName": ifc.name, "sizeBytes": ifc.stat().st_size}
        for ifc in sorted(OUTPUT_DIR.glob("*.ifc"), key=lambda path: path.name.lower())
    ]
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(models, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote manifest.json with {len(models)} models")


if __name__ == "__main__":
    main()
