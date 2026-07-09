#!/usr/bin/env python3
"""Render a yEd SDL graphml page to SVG, faithfully to the drawn figure.

The graphml files in spec-sdl/**/sdl/ carry everything needed to reproduce
the drawing: node geometry, the 13-shape SDL palette as embedded SVG
resources (scaled to each node's visual bounds, matching yEd's
usingVisualBounds="true"), polyline edge paths with source/target offsets,
and node/edge labels. This tool re-renders that into a standalone SVG with
no external dependencies (Python stdlib only), deterministically — the same
graphml always produces byte-identical output, so renders can be committed
as generated artifacts and drift-checked in CI like every other backend.

Viewports: a `viewports.json` sidecar next to the graphml names crops
(anchor node ids + padding) that correspond to regions of the original
paged spec figures, so a PR reviewer can look at just the affected column.

Usage:
  render_graphml_svg.py INPUT.graphml -o OUT.svg              # full page
  render_graphml_svg.py INPUT.graphml -o OUT.svg --viewport NAME
  render_graphml_svg.py INPUT.graphml -o OUT.svg --nodes n205,n233 --pad 60
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

G = "{http://graphml.graphdrawing.org/xmlns}"
Y = "{http://www.yworks.com/xml/graphml}"
SVGNS = "http://www.w3.org/2000/svg"

FONT_FAMILY = "Helvetica, Arial, sans-serif"
LINE_PITCH = 1.256  # yEd's ~15.09px line height at fontSize 12


# ── geometry helpers ─────────────────────────────────────────────────────


def parse_transform(s):
    """Return a 3x3 affine matrix (as 6-tuple a,b,c,d,e,f) for an SVG
    transform attribute supporting translate/scale/matrix chains."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        vals = [float(v) for v in re.split(r"[,\s]+", args.strip()) if v]
        if name == "translate":
            tx = vals[0]
            ty = vals[1] if len(vals) > 1 else 0.0
            n = (1, 0, 0, 1, tx, ty)
        elif name == "scale":
            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else sx
            n = (sx, 0, 0, sy, 0, 0)
        elif name == "matrix" and len(vals) == 6:
            n = tuple(vals)
        else:
            continue
        a1, b1, c1, d1, e1, f1 = m
        a2, b2, c2, d2, e2, f2 = n
        m = (
            a1 * a2 + c1 * b2,
            b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2,
            b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1,
            b1 * e2 + d1 * f2 + f1,
        )
    return m


def apply_matrix(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


_PATH_TOKEN = re.compile(r"([MmLlHhVvZzCcSsQqTtAa])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def path_points(d):
    """Yield the on-path / control points of a path `d` string (bounds
    approximation: curve control points over-approximate the hull)."""
    cmd = None
    cx = cy = sx = sy = 0.0
    nums = []
    need = {
        "M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7,
    }
    for tok_cmd, tok_num in _PATH_TOKEN.findall(d):
        if tok_cmd:
            if tok_cmd in "Zz":
                cx, cy = sx, sy
                cmd = None
                nums = []
                continue
            cmd = tok_cmd
            nums = []
            continue
        if cmd is None:
            continue
        nums.append(float(tok_num))
        n = need[cmd.upper()]
        if len(nums) < n:
            continue
        rel = cmd.islower()
        u = cmd.upper()
        if u == "H":
            cx = cx + nums[0] if rel else nums[0]
            yield (cx, cy)
        elif u == "V":
            cy = cy + nums[0] if rel else nums[0]
            yield (cx, cy)
        elif u == "A":
            x, y = nums[5], nums[6]
            cx, cy = (cx + x, cy + y) if rel else (x, y)
            yield (cx, cy)
        else:
            pts = [(nums[i], nums[i + 1]) for i in range(0, n, 2)]
            for px, py in pts:
                x, y = (cx + px, cy + py) if rel else (px, py)
                yield (x, y)
            cx, cy = (
                (cx + pts[-1][0], cy + pts[-1][1]) if rel else pts[-1]
            )
            if u == "M":
                sx, sy = cx, cy
                cmd = "l" if rel else "L"
        nums = []


def element_points(el, m):
    """Yield transformed boundary points for basic SVG shape elements."""
    tag = el.tag.split("}")[-1]
    m = compose(m, parse_transform(el.get("transform")))
    if tag == "path" and el.get("d"):
        for x, y in path_points(el.get("d")):
            yield apply_matrix(m, x, y)
    elif tag == "rect":
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        w, h = float(el.get("width", 0)), float(el.get("height", 0))
        for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            yield apply_matrix(m, px, py)
    elif tag in ("ellipse", "circle"):
        cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
        rx = float(el.get("rx", el.get("r", 0)))
        ry = float(el.get("ry", el.get("r", 0)))
        for px, py in ((cx - rx, cy - ry), (cx + rx, cy + ry)):
            yield apply_matrix(m, px, py)
    elif tag in ("polygon", "polyline") and el.get("points"):
        vals = [float(v) for v in re.split(r"[,\s]+", el.get("points").strip()) if v]
        for i in range(0, len(vals) - 1, 2):
            yield apply_matrix(m, vals[i], vals[i + 1])
    elif tag == "line":
        for px, py in (
            (float(el.get("x1", 0)), float(el.get("y1", 0))),
            (float(el.get("x2", 0)), float(el.get("y2", 0))),
        ):
            yield apply_matrix(m, px, py)
    for child in el:
        yield from element_points(child, m)


def compose(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def content_bounds(svg_root):
    """Visual bounds of an SVG resource's drawn content — the region yEd
    scales to the node box when usingVisualBounds="true"."""
    pts = list(element_points(svg_root, IDENTITY))
    if not pts:
        vb = (svg_root.get("viewBox") or "0 0 120 60").split()
        return float(vb[0]), float(vb[1]), float(vb[2]), float(vb[3])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


# ── graphml model ────────────────────────────────────────────────────────


class Node:
    __slots__ = ("id", "x", "y", "w", "h", "refid", "labels")


class Edge:
    __slots__ = ("id", "src", "tgt", "sx", "sy", "tx", "ty", "bends", "labels")


def load(path):
    tree = ET.parse(path)
    root = tree.getroot()

    resources = {}
    for res in root.findall(f".//{Y}Resources/{Y}Resource"):
        resources[res.get("id")] = res.text or ""

    graph = root.find(f"{G}graph")
    nodes, edges = {}, []
    for n in graph.findall(f"{G}node"):
        svgnode = n.find(f".//{Y}SVGNode")
        if svgnode is None:
            continue
        geo = svgnode.find(f"{Y}Geometry")
        node = Node()
        node.id = n.get("id")
        node.x, node.y = float(geo.get("x")), float(geo.get("y"))
        node.w, node.h = float(geo.get("width")), float(geo.get("height"))
        content = svgnode.find(f"{Y}SVGModel/{Y}SVGContent")
        node.refid = content.get("refid") if content is not None else None
        node.labels = []
        for lab in svgnode.findall(f"{Y}NodeLabel"):
            if lab.get("visible") == "false":
                continue
            node.labels.append(
                {
                    "text": "".join(lab.itertext()),
                    "x": float(lab.get("x", 0)),
                    "y": float(lab.get("y", 0)),
                    "w": float(lab.get("width", node.w)),
                    "size": float(lab.get("fontSize", 12)),
                }
            )
        nodes[node.id] = node

    for e in graph.findall(f"{G}edge"):
        pl = e.find(f".//{Y}PolyLineEdge")
        edge = Edge()
        edge.id = e.get("id")
        edge.src, edge.tgt = e.get("source"), e.get("target")
        edge.sx = edge.sy = edge.tx = edge.ty = 0.0
        edge.bends = []
        edge.labels = []
        if pl is not None:
            p = pl.find(f"{Y}Path")
            if p is not None:
                edge.sx, edge.sy = float(p.get("sx", 0)), float(p.get("sy", 0))
                edge.tx, edge.ty = float(p.get("tx", 0)), float(p.get("ty", 0))
                edge.bends = [
                    (float(pt.get("x")), float(pt.get("y")))
                    for pt in p.findall(f"{Y}Point")
                ]
            for lab in pl.findall(f"{Y}EdgeLabel"):
                if lab.get("visible") == "false":
                    continue
                edge.labels.append(
                    {
                        "text": "".join(lab.itertext()).strip(),
                        "x": float(lab.get("x", 0)),
                        "y": float(lab.get("y", 0)),
                        "w": float(lab.get("width", 0)),
                        "h": float(lab.get("height", 0)),
                        "size": float(lab.get("fontSize", 12)),
                    }
                )
        edges.append(edge)

    return nodes, edges, resources


# ── edge routing ─────────────────────────────────────────────────────────


def clip_to_rect(inside, outside, rect):
    """Point where segment inside→outside crosses the rect border."""
    x0, y0 = inside
    x1, y1 = outside
    rx, ry, rw, rh = rect
    best_t = 1.0
    dx, dy = x1 - x0, y1 - y0
    for edge_val, delta, lo, hi, cross in (
        (rx, dx, ry, ry + rh, "v"),
        (rx + rw, dx, ry, ry + rh, "v"),
        (ry, dy, rx, rx + rw, "h"),
        (ry + rh, dy, rx, rx + rw, "h"),
    ):
        if abs(delta) < 1e-9:
            continue
        t = ((edge_val - (x0 if cross == "v" else y0)) / delta)
        if t <= 1e-9 or t > 1:
            continue
        px, py = x0 + dx * t, y0 + dy * t
        ok = lo - 0.5 <= (py if cross == "v" else px) <= hi + 0.5
        if ok and t < best_t:
            best_t = t
    return (x0 + dx * best_t, y0 + dy * best_t)


def edge_polyline(edge, nodes):
    s, t = nodes[edge.src], nodes[edge.tgt]
    scx, scy = s.x + s.w / 2 + edge.sx, s.y + s.h / 2 + edge.sy
    tcx, tcy = t.x + t.w / 2 + edge.tx, t.y + t.h / 2 + edge.ty
    pts = [(scx, scy)] + edge.bends + [(tcx, tcy)]
    pts[0] = clip_to_rect(pts[0], pts[1], (s.x, s.y, s.w, s.h))
    pts[-1] = clip_to_rect(pts[-1], pts[-2], (t.x, t.y, t.w, t.h))
    return pts


# ── resource embedding ───────────────────────────────────────────────────

_STRIP_NS = re.compile(r"\{[^}]*\}")


def sanitize(el):
    """Deep-copy an element keeping only SVG-namespace tags/attributes."""
    tag = el.tag
    if not isinstance(tag, str):
        return None
    if tag.startswith("{") and not tag.startswith("{" + SVGNS + "}"):
        return None
    out = ET.Element(_STRIP_NS.sub("", tag))
    for k, v in el.attrib.items():
        if k.startswith("{"):
            continue
        if k in ("id",):
            continue
        out.set(k, v)
    out.text, out.tail = el.text, el.tail
    for child in el:
        c = sanitize(child)
        if c is not None:
            out.append(c)
    return out


def resource_group(res_text, cache={}):
    """Parse a resource SVG once; return (inner_group_element, bounds)."""
    key = id(res_text)
    if key in cache:
        return cache[key]
    root = ET.fromstring(res_text)
    bounds = content_bounds(root)
    group = ET.Element("g")
    for child in root:
        tag = child.tag.split("}")[-1]
        if tag in ("title", "defs", "metadata", "namedview"):
            continue
        c = sanitize(child)
        if c is not None:
            group.append(c)
    cache[key] = (group, bounds)
    return cache[key]


# ── output ───────────────────────────────────────────────────────────────


def fnum(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


CHAR_W = 0.56  # average glyph width in em for Helvetica-ish text


def est_width(text, size):
    return len(text) * size * CHAR_W


def wrap_line(text, size, max_w):
    """Greedy word-wrap to max_w, mirroring yEd's node-width CroppingLabel
    (the stored label heights in the graphml match this wrapping)."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if cur and est_width(cand, size) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def esc(s):
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def rects_intersect(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def render(nodes, edges, resources, crop=None, pad=0.0, restrict=None):
    if restrict:
        nodes = {i: n for i, n in nodes.items() if i in restrict}
        edges = [e for e in edges if e.src in restrict and e.tgt in restrict]
    if crop:
        min_x, min_y, max_x, max_y = crop
        for e in edges:
            if e.src not in nodes or e.tgt not in nodes:
                continue
            s, t = nodes[e.src], nodes[e.tgt]
            if rects_intersect(
                (s.x, s.y, s.w, s.h), (min_x, min_y, max_x - min_x, max_y - min_y)
            ) and rects_intersect(
                (t.x, t.y, t.w, t.h), (min_x, min_y, max_x - min_x, max_y - min_y)
            ):
                # keep in-view elbows visible
                for bx, by in e.bends:
                    min_x, min_y = min(min_x, bx), min(min_y, by)
                    max_x, max_y = max(max_x, bx), max(max_y, by)
    else:
        min_x = min(n.x for n in nodes.values())
        min_y = min(n.y for n in nodes.values())
        max_x = max(n.x + n.w for n in nodes.values())
        max_y = max(n.y + n.h for n in nodes.values())
        for e in edges:
            for bx, by in e.bends:
                min_x, min_y = min(min_x, bx), min(min_y, by)
                max_x, max_y = max(max_x, bx), max(max_y, by)
        pad = max(pad, 20.0)
    min_x, min_y, max_x, max_y = (
        min_x - pad, min_y - pad, max_x + pad, max_y + pad
    )
    w, h = max_x - min_x, max_y - min_y

    out = []
    out.append(
        f'<svg xmlns="{SVGNS}" width="{fnum(w)}" height="{fnum(h)}" '
        f'viewBox="{fnum(min_x)} {fnum(min_y)} {fnum(w)} {fnum(h)}" '
        f'font-family="{FONT_FAMILY}">'
    )
    out.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 1 L 9 5 L 0 9 z" fill="#000000"/></marker></defs>'
    )
    out.append(
        f'<rect x="{fnum(min_x)}" y="{fnum(min_y)}" width="{fnum(w)}" '
        f'height="{fnum(h)}" fill="#FFFFFF"/>'
    )

    view_rect = (min_x, min_y, max_x - min_x, max_y - min_y)

    # edges under nodes
    for e in edges:
        if e.src not in nodes or e.tgt not in nodes:
            continue
        if crop:
            # A cropped render only keeps edges with at least one endpoint
            # in view — otherwise unrelated columns' edges slash across it.
            s, t = nodes[e.src], nodes[e.tgt]
            if not (
                rects_intersect((s.x, s.y, s.w, s.h), view_rect)
                or rects_intersect((t.x, t.y, t.w, t.h), view_rect)
            ):
                continue
        pts = edge_polyline(e, nodes)
        d = "M " + " L ".join(f"{fnum(x)} {fnum(y)}" for x, y in pts)
        out.append(
            f'<path d="{d}" fill="none" stroke="#000000" stroke-width="1" '
            'marker-end="url(#arrow)"/>'
        )
        s_rect = (nodes[e.src].x, nodes[e.src].y, nodes[e.src].w, nodes[e.src].h)
        t_rect = (nodes[e.tgt].x, nodes[e.tgt].y, nodes[e.tgt].w, nodes[e.tgt].h)
        for lab in e.labels:
            if not lab["text"]:
                continue
            lx = pts[0][0] + lab["x"] + lab["w"] / 2
            ly = pts[0][1] + lab["y"] + lab["h"] / 2
            lab_rect = (lx - lab["w"] / 2, ly - lab["h"] / 2, lab["w"], lab["h"])
            if rects_intersect(lab_rect, s_rect) or rects_intersect(lab_rect, t_rect):
                # The cached yEd offset lands on a node — fall back to the
                # first segment's midpoint, offset perpendicular to the line.
                (x0, y0), (x1, y1) = pts[0], pts[1]
                seg = math.hypot(x1 - x0, y1 - y0) or 1.0
                px, py = -(y1 - y0) / seg, (x1 - x0) / seg
                for side in (1.0, -1.0):
                    lx = (x0 + x1) / 2 + px * 14 * side
                    ly = (y0 + y1) / 2 + py * 14 * side
                    lab_rect = (
                        lx - lab["w"] / 2, ly - lab["h"] / 2, lab["w"], lab["h"]
                    )
                    if not (
                        rects_intersect(lab_rect, s_rect)
                        or rects_intersect(lab_rect, t_rect)
                    ):
                        break
            # White halo keeps Yes/No branch labels legible where they
            # land on top of an edge line.
            out.append(
                f'<text x="{fnum(lx)}" y="{fnum(ly + lab["size"] * 0.35)}" '
                f'font-size="{fnum(lab["size"])}" '
                'text-anchor="middle" stroke="#FFFFFF" stroke-width="3" '
                f'paint-order="stroke">{esc(lab["text"])}</text>'
            )

    for n in nodes.values():
        res = resources.get(n.refid)
        if res:
            group, (bx, by, bw, bh) = resource_group(res)
            sx = n.w / bw if bw else 1.0
            sy = n.h / bh if bh else 1.0
            g = ET.Element("g")
            g.set(
                "transform",
                f"translate({fnum(n.x)} {fnum(n.y)}) scale({fnum(sx)} {fnum(sy)}) "
                f"translate({fnum(-bx)} {fnum(-by)})",
            )
            # keep stroke width visually ~1px despite scaling
            g.set("style", f"stroke-width:{fnum(1.0 / max(sx, sy))}")
            for child in group:
                g.append(child)
            out.append(ET.tostring(g, encoding="unicode"))
        else:
            out.append(
                f'<rect x="{fnum(n.x)}" y="{fnum(n.y)}" width="{fnum(n.w)}" '
                f'height="{fnum(n.h)}" fill="#FFFFFF" stroke="#000000"/>'
            )
        for lab in n.labels:
            size = lab["size"]
            max_w = lab["w"] - 4
            lines = []
            for raw in lab["text"].split("\n"):
                lines.extend(wrap_line(raw, size, max_w))
            longest = max((est_width(ln, size) for ln in lines), default=0.0)
            if longest > max_w + 2:
                size = max(8.0, size * (max_w + 2) / longest)
            pitch = size * LINE_PITCH
            cx = n.x + lab["x"] + lab["w"] / 2
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                ly = n.y + lab["y"] + size + i * pitch
                out.append(
                    f'<text x="{fnum(cx)}" y="{fnum(ly)}" font-size="{fnum(size)}" '
                    f'text-anchor="middle">{esc(line)}</text>'
                )

    out.append("</svg>")
    return "\n".join(out) + "\n"


# ── CLI ──────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--viewport", help="named viewport from viewports.json")
    ap.add_argument("--nodes", help="comma-separated anchor node ids for an ad-hoc crop")
    ap.add_argument("--pad", type=float, default=60.0)
    args = ap.parse_args()

    nodes, edges, resources = load(args.input)

    crop = None
    pad = args.pad
    anchor_ids = None
    restrict_to_anchors = False
    if args.viewport:
        sidecar = args.input.parent / "viewports.json"
        vps = json.loads(sidecar.read_text())
        page = vps.get(args.input.stem, {})
        if args.viewport not in page:
            sys.exit(
                f"viewport '{args.viewport}' not defined for {args.input.stem} in {sidecar}"
            )
        vp = page[args.viewport]
        anchor_ids = vp["nodes"]
        pad = float(vp.get("pad", pad))
        restrict_to_anchors = bool(vp.get("restrict", False))
    elif args.nodes:
        anchor_ids = args.nodes.split(",")

    if anchor_ids:
        # Tolerate anchors that no longer exist: figure corrections delete
        # nodes, and the viewport definition must survive that without every
        # consumer editing the sidecar in lockstep.
        missing = [i for i in anchor_ids if i not in nodes]
        present = [i for i in anchor_ids if i in nodes]
        if missing:
            print(
                f"warning: viewport anchors not in graph, ignored: {','.join(missing)}",
                file=sys.stderr,
            )
        if not present:
            sys.exit("no viewport anchor nodes exist in the graph")
        crop = (
            min(nodes[i].x for i in present),
            min(nodes[i].y for i in present),
            max(nodes[i].x + nodes[i].w for i in present),
            max(nodes[i].y + nodes[i].h for i in present),
        )

    svg = render(
        nodes, edges, resources, crop=crop, pad=pad,
        restrict=set(anchor_ids) if (anchor_ids and restrict_to_anchors) else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg)
    print(f"{args.input} -> {args.output}")


if __name__ == "__main__":
    main()
