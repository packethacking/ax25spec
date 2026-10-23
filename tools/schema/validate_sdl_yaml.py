#!/usr/bin/env python3
"""Validate every spec-sdl/**/*.sdl.yaml against its JSON Schema.

State pages are checked against spec-sdl/schema/sdl-machine.schema.json and
subroutines pages (a top-level `subroutines:` key) against
sdl-subroutines.schema.json. The yaml is read with YAML 1.2 booleans, so
`on:` and `branch: Yes` stay strings as the transcriber means them (PyYAML's
default YAML 1.1 rules would turn them into booleans).

Usage: python3 tools/schema/validate_sdl_yaml.py [repo-root]
Needs: pip install jsonschema pyyaml
"""
import json
import pathlib
import re
import sys

import jsonschema
import yaml


class Yaml12Loader(yaml.SafeLoader):
    """SafeLoader with only true/false as booleans."""


Yaml12Loader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    schema_dir = root / "spec-sdl" / "schema"
    machine = jsonschema.Draft202012Validator(
        json.loads((schema_dir / "sdl-machine.schema.json").read_text()))
    subroutines = jsonschema.Draft202012Validator(
        json.loads((schema_dir / "sdl-subroutines.schema.json").read_text()))

    pages = sorted((root / "spec-sdl").rglob("*.sdl.yaml"))
    if not pages:
        print("::error::no spec-sdl/**/*.sdl.yaml files found")
        return 1

    failures = 0
    for page in pages:
        doc = yaml.load(page.read_text(encoding="utf-8"), Loader=Yaml12Loader)
        validator = subroutines if "subroutines" in doc else machine
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        rel = page.relative_to(root)
        if not errors:
            print(f"ok    {rel}")
            continue
        failures += len(errors)
        for e in errors:
            where = "/".join(str(p) for p in e.absolute_path) or "(top)"
            print(f"::error file={rel}::{where}: {e.message}")
    print(f"{len(pages)} pages, {failures} schema error(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
