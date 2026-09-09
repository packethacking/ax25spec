"""Structural model of a yEd/SDL-style SVG: nodes, free labels, edges.

Nodes are `<g transform="translate(..) scale(..) translate(..)">` wrapping one
shape; labels are absolutely-positioned <text>; edges are top-level <path>/<line>.
Signatures are position-independent, so an auto-layout reflow does not register
as a change -- only genuinely added/removed content does.
"""
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

SVG = "{http://www.w3.org/2000/svg}"
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _f(el, attr, default=0.0):
    v = el.get(attr)
    return float(v) if v not in (None, "") else default


def _transform(t):
    """Return (tx, ty, sx, sy) for 'translate(a b) scale(sx sy) translate(cx cy)'."""
    tx = ty = 0.0
    sx = sy = 1.0
    for kind, body in re.findall(r"(translate|scale)\(([^)]*)\)", t or ""):
        n = [float(x) for x in NUM.findall(body)]
        if kind == "translate":
            a, b = (n + [0.0, 0.0])[:2]
            tx += sx * a
            ty += sy * b
        else:
            a = n[0]
            b = n[1] if len(n) > 1 else a
            sx *= a
            sy *= b
    return tx, ty, sx, sy


def _ellipse_ring(cx, cy, rx, ry, steps=32):
    return [(cx + rx * math.cos(2 * math.pi * k / steps),
             cy + ry * math.sin(2 * math.pi * k / steps)) for k in range(steps)]


def _inside(pt, ring):
    """Ray-cast point-in-polygon."""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i - 1) % n]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / ((by - ay) or 1e-12) + ax:
            inside = not inside
    return inside


def _shape(el):
    """(kind, width, height, extra, x, y, ring) in the element's own coordinates.

    `ring` is the ordered outline. A bounding box over-claims a diamond's
    corners by nearly half the node's width, which is exactly where edge
    labels sit, so label ownership has to test the real outline.
    """
    tag = el.tag.replace(SVG, "")
    if tag == "rect":
        rx = round(_f(el, "rx"), 1)
        x, y = _f(el, "x"), _f(el, "y")
        w, h = _f(el, "width"), _f(el, "height")
        return tag, w, h, f"r{rx}", x, y, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if tag == "ellipse":
        cx, cy, rx, ry = _f(el, "cx"), _f(el, "cy"), _f(el, "rx"), _f(el, "ry")
        return tag, 2 * rx, 2 * ry, "", cx - rx, cy - ry, _ellipse_ring(cx, cy, rx, ry)
    if tag == "circle":
        cx, cy, r = _f(el, "cx"), _f(el, "cy"), _f(el, "r")
        return tag, 2 * r, 2 * r, "", cx - r, cy - r, _ellipse_ring(cx, cy, r, r)
    if tag == "polygon":
        pts = [float(x) for x in NUM.findall(el.get("points", ""))]
        xs, ys = pts[0::2], pts[1::2]
        if not xs:
            return None
        # normalise the outline so identical shapes at different sizes still differ,
        # but identical shapes anywhere match
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        norm = " ".join(f"{(x - min(xs)) / (w or 1):.2f},{(y - min(ys)) / (h or 1):.2f}"
                        for x, y in zip(xs, ys))
        return tag, w, h, norm, min(xs), min(ys), list(zip(xs, ys))
    if tag == "path":
        pts = [float(x) for x in NUM.findall(el.get("d", ""))]
        xs, ys = pts[0::2], pts[1::2]
        if not xs:
            return None
        # A path's ring falls back to its box: the numbers in `d` cannot be paired
        # into vertices without a full path parser, and H/V/A make that non-trivial.
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        return (tag, x1 - x0, y1 - y0, "", x0, y0,
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return None


def _text_of(el):
    return "".join(el.itertext()).strip()


class Model:
    def __init__(self, svg_bytes):
        root = ET.fromstring(svg_bytes)
        vb = [float(x) for x in NUM.findall(root.get("viewBox", "0 0 0 0"))]
        self.ox, self.oy = vb[0], vb[1]
        self.width, self.height = vb[2], vb[3]
        self.nodes, self.edges, self.texts = [], [], []
        self._walk(root)
        self._attach_labels()

    def _box(self, x, y, w, h):
        return [round(x - self.ox, 1), round(y - self.oy, 1), round(w, 1), round(h, 1)]

    def _walk(self, root):
        for g in root.findall(f"{SVG}g"):
            tx, ty, sx, sy = _transform(g.get("transform"))
            sh = None
            for el in g.iter():
                sh = _shape(el)
                if sh:
                    break
            if not sh:
                continue
            kind, w, h, extra, lx, ly, ring = sh
            self.nodes.append({
                "sig": (kind, round(w, 1), round(h, 1), extra),
                "box": self._box(tx + sx * lx, ty + sy * ly, w * sx, h * sy),
                "ring": [(tx + sx * px - self.ox, ty + sy * py - self.oy)
                         for px, py in ring],
                "labels": [],
            })
        for tag in ("path", "line"):
            for el in root.findall(f"{SVG}{tag}"):
                if tag == "line":
                    pts = [_f(el, "x1"), _f(el, "y1"), _f(el, "x2"), _f(el, "y2")]
                else:
                    pts = [float(x) for x in NUM.findall(el.get("d", ""))]
                if len(pts) < 4:
                    continue
                xs, ys = pts[0::2], pts[1::2]
                self.edges.append({
                    "a": (xs[0], ys[0]), "b": (xs[-1], ys[-1]),
                    "dashed": bool(el.get("stroke-dasharray")),
                    "box": self._box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)),
                })
        for el in root.findall(f"{SVG}text"):
            t = _text_of(el)
            if t:
                self.texts.append({"t": t, "x": _f(el, "x"), "y": _f(el, "y")})

    def _attach_labels(self):
        """Give each text to the node whose box contains it; the rest are edge labels."""
        self.free = []
        for t in self.texts:
            x, y = t["x"] - self.ox, t["y"] - self.oy
            owner = None
            for n in self.nodes:
                bx, by, bw, bh = n["box"]
                # inset: a node's own caption sits well inside it, whereas an edge
                # label often grazes a node's bounding box without belonging to it
                ix, iy = min(10.0, bw / 4), min(6.0, bh / 4)
                if not (bx + ix <= x <= bx + bw - ix and by + iy <= y <= by + bh - iy):
                    continue
                # ...and on a diamond the inset box still over-claims the corners,
                # which is where edge labels sit. Confirm against the real outline.
                # Strictly narrowing: this can only reject a claim, never add one.
                if _inside((x, y), n["ring"]):
                    owner = n
                    break
            if owner:
                owner["labels"].append(t["t"])
            else:
                self.free.append(t)
        for n in self.nodes:
            n["label"] = " ".join(n["labels"])
            n["sig"] = n["sig"] + (n["label"],)
        # Anchoring needs the node labels above, so it is a second pass.
        for t in self.free:
            t["anchor"] = self.nearest((t["x"], t["y"]), max_dist=220)

    def nearest(self, pt, max_dist=60):
        """Label of the node closest to a point (for naming edge endpoints)."""
        x, y = pt[0] - self.ox, pt[1] - self.oy
        best, bd = None, 1e18
        for n in self.nodes:
            bx, by, bw, bh = n["box"]
            dx = max(bx - x, 0, x - (bx + bw))
            dy = max(by - y, 0, y - (by + bh))
            d = dx * dx + dy * dy
            if d < bd:
                best, bd = n, d
            if d == 0:
                break
        if best is None or bd > max_dist * max_dist:
            return "(unattached)"
        return (best["label"] or "(unlabelled)")[:60]

    def edge_sigs(self):
        out = defaultdict(list)
        for e in self.edges:
            sig = (self.nearest(e["a"]), self.nearest(e["b"]), e["dashed"])
            out[sig].append(e)
        return out


def _multidiff(old_items, new_items, *keys):
    """Return (added, removed) after cancelling old/new pairs.

    Each key in turn is one cancellation pass, finest first. A fine key (a
    label's text *and* the node it sits by) picks the right instance to
    report; a coarser fallback (the text alone) still cancels an item whose
    anchor merely moved, so a reflow cannot invent an add/remove pair.
    Matching by the coarse key alone would keep the counts right but report
    an arbitrary instance -- and so point the reviewer at the wrong place.
    """
    old_left, new_left = list(old_items), list(new_items)
    for key in keys:
        buckets = defaultdict(list)
        for i in old_left:
            buckets[key(i)].append(i)
        matched, survivors = set(), []
        for i in new_left:
            bucket = buckets.get(key(i))
            if bucket:
                matched.add(id(bucket.pop()))
            else:
                survivors.append(i)
        new_left = survivors
        old_left = [i for i in old_left if id(i) not in matched]
    return new_left, old_left


def diff(old_bytes, new_bytes):
    o, n = Model(old_bytes), Model(new_bytes)
    regions = []

    add, rem = _multidiff(o.nodes, n.nodes, lambda x: x["sig"])
    for src, kind in ((add, "added"), (rem, "removed")):
        for x in src:
            regions.append({"kind": kind, "what": "node", "side": "new" if kind == "added" else "old",
                            "box": x["box"], "text": x["label"] or f'({x["sig"][0]} shape)'})

    add, rem = _multidiff(o.free, n.free,
                          lambda x: (x["t"], x["anchor"]), lambda x: x["t"])
    for src, kind in ((add, "added"), (rem, "removed")):
        for x in src:
            regions.append({"kind": kind, "what": "label", "side": "new" if kind == "added" else "old",
                            "box": [round(x["x"] - (n if kind == "added" else o).ox - 40, 1),
                                    round(x["y"] - (n if kind == "added" else o).oy - 16, 1), 80.0, 22.0],
                            "text": (f'{x["t"]}  (by {x["anchor"]})'
                                     if x["anchor"] != "(unattached)" else x["t"])})

    oe, ne = o.edge_sigs(), n.edge_sigs()
    for sig in set(ne) - set(oe):
        for e in ne[sig][:1]:
            regions.append({"kind": "added", "what": "edge", "side": "new", "box": e["box"],
                            "text": f"{sig[0]} → {sig[1]}"})
    for sig in set(oe) - set(ne):
        for e in oe[sig][:1]:
            regions.append({"kind": "removed", "what": "edge", "side": "old", "box": e["box"],
                            "text": f"{sig[0]} → {sig[1]}"})

    order = {"node": 0, "label": 1, "edge": 2}
    regions.sort(key=lambda r: (order[r["what"]], r["kind"], r["text"]))
    stats = {
        "old": {"nodes": len(o.nodes), "edges": len(o.edges), "labels": len(o.free)},
        "new": {"nodes": len(n.nodes), "edges": len(n.edges), "labels": len(n.free)},
    }
    return regions, stats
