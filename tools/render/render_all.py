#!/usr/bin/env python3
"""Regenerate every committed SVG render from the graphml sources.

Walks spec-sdl/**/sdl/*.graphml, renders each page to a full-page SVG in the
sibling svg/ directory, plus one cropped SVG per named viewport defined in
the sdl/ directory's viewports.json. Deterministic; CI's render-drift job
runs exactly this and asserts `git diff --exit-code -- 'spec-sdl/**/svg/'`.

Usage (from the repo root):
  python3 tools/render/render_all.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_graphml_svg as rgs  # noqa: E402


def main():
    repo = Path(__file__).resolve().parents[2]
    graphmls = sorted((repo / "spec-sdl").glob("**/sdl/*.graphml"))
    if not graphmls:
        sys.exit("no graphml files found under spec-sdl/**/sdl/")
    for gml in graphmls:
        # The all-shapes palette reference isn't a state-machine page.
        if "all-shapes" in gml.name:
            continue
        out_dir = gml.parent.parent / "svg"
        out_dir.mkdir(parents=True, exist_ok=True)
        nodes, edges, resources = rgs.load(gml)

        full = rgs.render(nodes, edges, resources)
        (out_dir / f"{gml.stem}.svg").write_text(full)
        print(f"{gml.relative_to(repo)} -> {(out_dir / (gml.stem + '.svg')).relative_to(repo)}")

        sidecar = gml.parent / "viewports.json"
        if not sidecar.exists():
            continue
        for vp_name, vp in json.loads(sidecar.read_text()).get(gml.stem, {}).items():
            present = [i for i in vp["nodes"] if i in nodes]
            missing = [i for i in vp["nodes"] if i not in nodes]
            if missing:
                print(
                    f"warning: {gml.stem}/{vp_name}: anchors not in graph, "
                    f"ignored: {','.join(missing)}",
                    file=sys.stderr,
                )
            if not present:
                sys.exit(f"{gml.stem}/{vp_name}: no anchor nodes exist")
            crop = (
                min(nodes[i].x for i in present),
                min(nodes[i].y for i in present),
                max(nodes[i].x + nodes[i].w for i in present),
                max(nodes[i].y + nodes[i].h for i in present),
            )
            svg = rgs.render(
                nodes, edges, resources,
                crop=crop,
                pad=float(vp.get("pad", 60.0)),
                restrict=set(present) if vp.get("restrict") else None,
            )
            out = out_dir / f"{gml.stem}.{vp_name}.svg"
            out.write_text(svg)
            print(f"{gml.relative_to(repo)} [{vp_name}] -> {out.relative_to(repo)}")


if __name__ == "__main__":
    main()
