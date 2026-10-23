"""DXF lesen und in neutrale Primitive (geometry.py) zerlegen."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf import colors as dxfcolors
from ezdxf import path as dxfpath
from ezdxf.entities import DXFGraphic
from ezdxf.math import Vec3

from .geometry import Arc, Drawing, Ellipse, Line, Polyline, Style, Terminal, Text

# $INSUNITS -> Millimeter je Zeichnungseinheit (0 = ohne Einheit, als mm behandelt)
UNITS_TO_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0000254, 9: 0.0254, 10: 914.4, 13: 0.001, 14: 100.0}

# QET kennt nur benannte Farben (customelementgraphicpart.cpp)
QET_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 128, 0),
    "blue": (0, 0, 255), "gray": (128, 128, 128), "brun": (139, 69, 19), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "lightgray": (211, 211, 211),
    "orange": (255, 165, 0), "purple": (128, 0, 128),
}

DEFAULT_TERMINAL_LAYER = "TERMINALS"
_UNIT_Z = Vec3(0, 0, 1)


class DxfReadError(Exception):
    pass


def list_layers(path: str | Path) -> list[str]:
    doc = _open(path)
    return sorted(layer.dxf.name for layer in doc.layers)


def read_dxf(
    path: str | Path,
    layers: set[str] | None = None,
    terminal_layer: str = DEFAULT_TERMINAL_LAYER,
    keep_colors: bool = False,
    tolerance: float | None = None,
) -> Drawing:
    """Liest den Modellbereich einer DXF.

    layers: nur diese Layer übernehmen (None = alle).
    terminal_layer: Punkte/Kreise auf diesem Layer werden zu QET-Anschlüssen.
    tolerance: maximale Sehnenabweichung beim Annähern von Kurven (Zeichnungseinheiten);
               None = automatisch aus der Zeichnungsgröße.
    """
    doc = _open(path)
    msp = doc.modelspace()
    drawing = Drawing(
        layers=sorted(layer.dxf.name for layer in doc.layers),
        units_to_mm=UNITS_TO_MM.get(doc.header.get("$INSUNITS", 0), 1.0),
        name=Path(path).stem,
    )
    if tolerance is None:
        tolerance = _auto_tolerance(msp)
    reader = _Reader(doc, drawing, layers, terminal_layer.upper(), keep_colors, tolerance)
    for entity in msp:
        reader.add(entity)
    return drawing


def _open(path: str | Path):
    try:
        return ezdxf.readfile(str(path))
    except IOError as exc:
        raise DxfReadError(f"Datei nicht lesbar: {exc}") from exc
    except ezdxf.DXFStructureError:
        # beschädigte oder ungewöhnliche Dateien: Reparaturmodus von ezdxf
        from ezdxf import recover

        try:
            doc, _auditor = recover.readfile(str(path))
            return doc
        except ezdxf.DXFStructureError as exc:
            raise DxfReadError(f"Keine gültige DXF-Datei: {exc}") from exc


def _auto_tolerance(msp) -> float:
    from ezdxf import bbox as dxfbbox

    try:
        ext = dxfbbox.extents(msp, fast=True)
        size = max(ext.size.x, ext.size.y) if ext.has_data else 0.0
    except Exception:
        size = 0.0
    return max(size / 2000.0, 1e-4) if size > 0 else 0.01


class _Reader:
    def __init__(self, doc, drawing: Drawing, layers, terminal_layer: str, keep_colors: bool, tol: float):
        self.doc = doc
        self.d = drawing
        self.layers = layers
        self.terminal_layer = terminal_layer
        self.keep_colors = keep_colors
        self.tol = tol

    # -- Hilfen -----------------------------------------------------------

    def _layer_of(self, e: DXFGraphic, parent_layer: str | None) -> str:
        layer = e.dxf.get("layer", "0")
        # Block-Inhalt auf Layer 0 erbt den Layer der Blockreferenz
        if layer == "0" and parent_layer:
            return parent_layer
        return layer

    def _style(self, e: DXFGraphic, layer: str, filled: bool = False) -> Style:
        layer_entry = self.doc.layers.get(layer) if self.doc.layers.has_entry(layer) else None

        ltype = (e.dxf.get("linetype", "BYLAYER") or "BYLAYER").upper()
        if ltype == "BYLAYER" and layer_entry is not None:
            ltype = (layer_entry.dxf.get("linetype", "CONTINUOUS") or "CONTINUOUS").upper()
        if "DASHDOT" in ltype or "CENTER" in ltype or "PHANTOM" in ltype or "DIVIDE" in ltype:
            line = "dashdotted"
        elif "DASH" in ltype or "HIDDEN" in ltype:
            line = "dashed"
        elif "DOT" in ltype:
            line = "dotted"
        else:
            line = "normal"

        color = "black"
        if self.keep_colors:
            color = self._color_name(e, layer_entry)
        return Style(line=line, color=color, filled=filled)

    def _color_name(self, e: DXFGraphic, layer_entry) -> str:
        rgb = e.rgb if e.dxf.hasattr("true_color") else None
        if rgb is None:
            aci = e.dxf.get("color", 256)
            if aci == 256 and layer_entry is not None:  # BYLAYER
                aci = abs(layer_entry.dxf.get("color", 7))
            if aci in (0, 7, 256):  # BYBLOCK / weiß-schwarz
                return "black"
            rgb = dxfcolors.aci2rgb(aci)
        r, g, b = rgb
        return min(QET_COLORS, key=lambda n: sum((a - c) ** 2 for a, c in zip((r, g, b), QET_COLORS[n])))

    def _from_path(self, e: DXFGraphic, style: Style, closed: bool | None = None) -> None:
        p = dxfpath.make_path(e)
        self._add_path(p, style, closed)

    def _add_path(self, p, style: Style, closed: bool | None = None) -> None:
        for sub in p.sub_paths() if p.has_sub_paths else [p]:
            pts = [(v.x, v.y) for v in sub.flattening(self.tol)]
            if len(pts) < 2:
                continue
            is_closed = sub.is_closed if closed is None else closed
            if is_closed and len(pts) > 2 and _same(pts[0], pts[-1]):
                pts.pop()
            self.d.primitives.append(Polyline(tuple(pts), is_closed, style))

    # -- Entitäten --------------------------------------------------------

    def add(self, e: DXFGraphic, parent_layer: str | None = None, depth: int = 0) -> None:
        kind = e.dxftype()
        layer = self._layer_of(e, parent_layer)

        if kind in ("INSERT", "DIMENSION", "ARC_DIMENSION", "LARGE_RADIAL_DIMENSION",
                    "LEADER", "MLEADER", "MULTILEADER", "ACAD_TABLE"):
            if self.layers is not None and kind != "INSERT" and layer not in self.layers:
                return
            if depth > 30:
                self.d.count(kind, skipped=True)
                return
            try:
                children = list(e.virtual_entities())
            except Exception:
                self.d.count(kind, skipped=True)
                return
            if kind == "INSERT":
                children += list(e.attribs)
            self.d.count(kind)
            for child in children:
                self.add(child, layer, depth + 1)
            return

        if self.layers is not None and layer not in self.layers:
            return
        if e.dxf.get("invisible", 0):
            return

        if layer.upper() == self.terminal_layer:
            if self._add_terminal(e, kind):
                return

        style = self._style(e, layer)
        handler = getattr(self, "_" + kind.lower(), None)
        if handler is None:
            self.d.count(kind, skipped=True)
            return
        try:
            ok = handler(e, style)
        except Exception:
            ok = False
        self.d.count(kind, skipped=ok is False)

    def _add_terminal(self, e: DXFGraphic, kind: str) -> bool:
        if kind == "POINT":
            p = e.dxf.location
        elif kind in ("CIRCLE", "ARC"):
            p = e.ocs().to_wcs(e.dxf.center)
        else:
            return False
        name = f"{len([t for t in self.d.primitives if isinstance(t, Terminal)]) + 1}"
        self.d.primitives.append(Terminal(p.x, p.y, name))
        self.d.count("Anschluss")
        return True

    def _line(self, e, style):
        s, t = e.dxf.start, e.dxf.end
        self.d.primitives.append(Line(s.x, s.y, t.x, t.y, style))

    def _circle(self, e, style):
        if not _is_planar(e):
            return self._from_path(e, style, True)
        c = e.dxf.center
        r = e.dxf.radius
        self.d.primitives.append(Ellipse(c.x, c.y, r, r, style))

    def _arc(self, e, style):
        if not _is_planar(e):
            return self._from_path(e, style, False)
        c = e.dxf.center
        r = e.dxf.radius
        start = e.dxf.start_angle % 360
        span = (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360
        self.d.primitives.append(Arc(c.x, c.y, r, r, start, span, style))

    def _ellipse(self, e, style):
        major = Vec3(e.dxf.major_axis)
        angle = math.degrees(math.atan2(major.y, major.x)) % 360
        aligned = min(abs(angle - a) for a in (0, 90, 180, 270, 360)) < 1e-6
        if not aligned or not Vec3(e.dxf.extrusion).isclose(_UNIT_Z):
            return self._from_path(e, style, None)
        a = major.magnitude
        b = a * e.dxf.ratio
        rx, ry = (a, b) if round(angle) % 180 == 0 else (b, a)
        c = e.dxf.center
        sp = math.degrees(e.dxf.start_param)
        ep = math.degrees(e.dxf.end_param)
        span = (ep - sp) % 360
        if span < 1e-6 or abs(span - 360) < 1e-6:
            self.d.primitives.append(Ellipse(c.x, c.y, rx, ry, style))
        else:
            # Parameterwinkel gegen die x-Achse: t + Richtung der Hauptachse
            self.d.primitives.append(Arc(c.x, c.y, rx, ry, (sp + angle) % 360, span, style))

    def _lwpolyline(self, e, style):
        self._polyline_like(e, style)

    def _polyline(self, e, style):
        if e.is_polygon_mesh or e.is_poly_face_mesh:
            return False
        self._polyline_like(e, style)

    def _polyline_like(self, e, style):
        closed = bool(e.closed if hasattr(e, "closed") else e.is_closed)
        filled = False
        self._from_path(e, Style(style.line, style.color, filled), closed)

    def _spline(self, e, style):
        self._from_path(e, style, bool(e.closed))

    def _helix(self, e, style):
        self._from_path(e, style, False)

    def _solid(self, e, style):
        vs = e.wcs_vertices()
        pts = [(v.x, v.y) for v in vs]
        dedup = [p for i, p in enumerate(pts) if i == 0 or not _same(p, pts[i - 1])]
        self.d.primitives.append(Polyline(tuple(dedup), True, Style(style.line, style.color, True)))

    _trace = _solid
    _3dface = _solid

    def _hatch(self, e, style):
        solid = bool(e.dxf.get("solid_fill", 0))
        for p in dxfpath.from_hatch(e):
            self._add_path(p, Style("normal", style.color, solid), True)

    _mpolygon = _hatch

    def _point(self, e, style):
        return False  # Punkte haben in QET kein Gegenstück (außer als Anschluss)

    def _text(self, e, style):
        text = e.plain_text().strip()
        if not text:
            return
        h = e.dxf.get("height", 2.5)
        rot = e.dxf.get("rotation", 0.0)
        halign = e.dxf.get("halign", 0)
        valign = e.dxf.get("valign", 0)
        p = Vec3(e.dxf.insert)
        if (halign or valign) and halign not in (3, 5) and e.dxf.hasattr("align_point"):
            p = Vec3(e.dxf.align_point)
        p = e.ocs().to_wcs(p)
        w = 0.6 * h * len(text)
        dx = {0: 0.0, 1: -w / 2, 2: -w, 3: 0.0, 4: -w / 2, 5: 0.0}.get(halign, 0.0)
        dy = {0: 0.0, 1: 0.0, 2: -h / 2, 3: -h}.get(valign, 0.0)
        if halign == 4:  # MIDDLE: mittig auch in der Höhe
            dy = -h / 2
        x, y = _rotate_offset(p.x, p.y, dx, dy, rot)
        self.d.primitives.append(Text(x, y, text, h, rot, style))

    _attrib = _text
    _attdef = _text

    def _mtext(self, e, style):
        text = e.plain_text().strip()
        if not text:
            return
        h = e.dxf.get("char_height", 2.5)
        rot = e.get_rotation()
        p = Vec3(e.dxf.insert)
        lines = text.split("\n")
        w = 0.6 * h * max(len(s) for s in lines)
        total = h * (1.67 * (len(lines) - 1) + 1)
        ap = e.dxf.get("attachment_point", 1)
        col, row = (ap - 1) % 3, (ap - 1) // 3
        dx = -w * col / 2
        # Grundlinie der obersten Zeile relativ zum Einfügepunkt
        dy = (-h, total / 2 - h, total - h)[row]
        x, y = _rotate_offset(p.x, p.y, dx, dy, rot)
        self.d.primitives.append(Text(x, y, text, h, rot, style))


def _rotate_offset(x: float, y: float, dx: float, dy: float, rot_deg: float) -> tuple[float, float]:
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    return x + dx * c - dy * s, y + dx * s + dy * c


def _is_planar(e) -> bool:
    return Vec3(e.dxf.get("extrusion", _UNIT_Z)).isclose(_UNIT_Z)


def _same(a, b, eps: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps
