"""Write the OpenAPI schema to web/ so the frontend's types can be generated.

Deliberately does not run a server: `app.openapi()` is an ordinary function, so
this needs no port, no database and no network. That matters because it runs in
CI as a drift check — regenerate, and fail if the committed schema differs.

The schema is committed rather than generated on the fly so that `npm` alone can
build the frontend, without a Python toolchain to hand.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import app

OUT = pathlib.Path(__file__).resolve().parents[2] / "web" / "src" / "api-schema.json"


def main() -> None:
    schema = app.openapi()
    # Stable formatting, so the CI diff is about content and never key order.
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    paths = len(schema.get("paths", {}))
    models = len(schema.get("components", {}).get("schemas", {}))
    print(f"wrote {OUT.relative_to(OUT.parents[2])}: {paths} paths, {models} models")


if __name__ == "__main__":
    main()
