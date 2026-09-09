#!/usr/bin/env python3
"""Structural + visual diff for the committed SVG figure renders.

The svg/ renders are auto-laid-out, so adding a single node reflows the whole
page: a plain pixel diff of one added decision diamond reports ~55 changed
regions and is useless for review. This tool diffs the *structure* instead --
nodes, edge endpoints and free labels are given position-independent
signatures, so pure layout movement cancels out and only genuinely added or
removed content is reported.

For each changed figure it prints the change list and writes a self-contained
HTML viewer (both renders embedded, no network, no dependencies) offering
new/old/swipe/onion/blink/difference views with a clickable change list that
zooms straight to each change.

Usage (from the repo root):
  # every SVG that differs between two revisions
  python3 tools/svgdiff/svg_diff.py main HEAD --all

  # a PR branch, against the point it forked from
  python3 tools/svgdiff/svg_diff.py main pr81 --all --merge-base

  # specific figures only
  python3 tools/svgdiff/svg_diff.py main HEAD spec-sdl/v2.2-errata/data-link/svg/DataLink_Connected.svg

  # change list only, for a CI comment
  python3 tools/svgdiff/svg_diff.py main HEAD --all --format markdown --no-html
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import svg_struct  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "viewer_template.html"


def git(*args: str, binary: bool = False):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def blob(rev: str, path: str) -> bytes | None:
    """File content at a revision, or None if it does not exist there."""
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def changed_svgs(oldrev: str, newrev: str) -> list[str]:
    out = git("diff", "--name-only", oldrev, newrev, "--", "*.svg")
    return [line for line in out.splitlines() if line.strip()]


def build_viewer(name: str, oldrev: str, newrev: str,
                 old_bytes: bytes, new_bytes: bytes, regions: list, stats: dict) -> str:
    struct = [
        {
            "kind": r["kind"], "what": r["what"], "side": r["side"], "text": r["text"],
            "x": r["box"][0] - 8, "y": r["box"][1] - 8,
            "w": r["box"][2] + 16, "h": r["box"][3] + 16,
        }
        for r in regions
    ]

    def data_uri(b: bytes) -> str:
        return "data:image/svg+xml;base64," + base64.b64encode(b).decode()

    return (TEMPLATE.read_text(encoding="utf-8")
            .replace("__STRUCT__", json.dumps(struct))
            .replace("__STATS__", json.dumps(stats))
            .replace("__OLD__", data_uri(old_bytes))
            .replace("__NEW__", data_uri(new_bytes))
            .replace("__NAME__", html.escape(name))
            .replace("__OLDREV__", html.escape(oldrev))
            .replace("__NEWREV__", html.escape(newrev)))


SIGN = {"added": "+", "removed": "−"}


def report_text(results: list[dict], oldrev: str, newrev: str) -> str:
    lines = []
    for res in results:
        lines.append(f"\n{res['path']}")
        if res["note"]:
            lines.append(f"  {res['note']}")
        for r in res["regions"]:
            lines.append(f"  {SIGN[r['kind']]} {r['what']:6} {r['text']}")
        if not res["regions"] and not res["note"]:
            lines.append("  layout changed, but no nodes, edges or labels added or removed")
        if res["html"]:
            lines.append(f"  viewer: {res['html']}")
    if not results:
        lines.append(f"no SVG differs between {oldrev} and {newrev}")
    return "\n".join(lines).lstrip("\n")


def report_markdown(results: list[dict], oldrev: str, newrev: str) -> str:
    if not results:
        return f"No SVG figure differs between `{oldrev}` and `{newrev}`."
    out = [f"### SVG figure changes (`{oldrev}` → `{newrev}`)", ""]
    for res in results:
        out.append(f"**`{res['path']}`**")
        if res["note"]:
            out.append("")
            out.append(f"_{res['note'].capitalize()}._")
            out.append("")
            continue
        st = res["stats"]
        out.append("")
        out.append(f"nodes {st['old']['nodes']}→{st['new']['nodes']}, "
                   f"edges {st['old']['edges']}→{st['new']['edges']}, "
                   f"labels {st['old']['labels']}→{st['new']['labels']}")
        out.append("")
        if not res["regions"]:
            out.append("_Layout reflowed; no nodes, edges or labels added or removed._")
            out.append("")
            continue
        out.append("| | what | change |")
        out.append("| --- | --- | --- |")
        for r in res["regions"]:
            text = r["text"].replace("|", "\\|")
            out.append(f"| {SIGN[r['kind']]} | {r['what']} | `{text}` |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Structural + visual diff for the committed SVG figure renders.")
    ap.add_argument("oldrev")
    ap.add_argument("newrev")
    ap.add_argument("paths", nargs="*", help="SVG paths; omit (or pass --all) for every changed SVG")
    ap.add_argument("--all", action="store_true",
                    help="diff every SVG that differs between the two revisions")
    ap.add_argument("--merge-base", action="store_true",
                    help="compare against the merge base of the two revisions, not oldrev's tip")
    ap.add_argument("--out", default="build/svgdiff",
                    help="directory for the generated viewers (default: build/svgdiff)")
    ap.add_argument("--format", choices=("text", "markdown"), default="text")
    ap.add_argument("--no-html", action="store_true", help="print the change list only")
    a = ap.parse_args()

    oldrev = a.oldrev
    if a.merge_base:
        oldrev = git("merge-base", a.oldrev, a.newrev).strip()

    paths = a.paths
    if a.all or not paths:
        paths = changed_svgs(oldrev, a.newrev)

    out_dir = (REPO / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    if not a.no_html and paths:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for path in paths:
        old_bytes, new_bytes = blob(oldrev, path), blob(a.newrev, path)
        res = {"path": path, "note": "", "regions": [], "stats": None, "html": None}
        if old_bytes is None or new_bytes is None:
            res["note"] = ("added in this change" if old_bytes is None
                           else "deleted in this change")
            results.append(res)
            continue
        if old_bytes == new_bytes:
            continue
        res["regions"], res["stats"] = svg_struct.diff(old_bytes, new_bytes)
        if not a.no_html:
            dest = out_dir / f"svgdiff-{Path(path).stem}.html"
            dest.write_text(
                build_viewer(Path(path).name, a.oldrev, a.newrev,
                             old_bytes, new_bytes, res["regions"], res["stats"]),
                encoding="utf-8")
            res["html"] = str(dest.relative_to(REPO)) if dest.is_relative_to(REPO) else str(dest)
        results.append(res)

    render = report_markdown if a.format == "markdown" else report_text
    text = render(results, a.oldrev, a.newrev)
    try:
        print(text)
    except UnicodeEncodeError:                      # legacy Windows console codepage
        sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
