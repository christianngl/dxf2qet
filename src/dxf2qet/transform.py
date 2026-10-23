"""DXF-Raum (Y nach oben, Zeichnungseinheiten) -> QET-Raum (Y nach unten, Pixel)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Arc, Drawing, Ellipse, Line, Polyline, Primitive, Terminal, Text, bbox


class EmptyDrawingError(Exception):
    pass


@dataclass
class Options:
    px_per_mm: float = 2.0  # Pixel je Millimeter der Zeichnung (A3-Plan passt aufs QET-Standardblatt)
    fit_px: float | None = None  # größte Seite auf diese Pixelzahl einpassen (ersetzt px_per_mm)
    grid: int = 10  # QET-Raster; Breite/Höhe/Hotspot werden darauf gerundet
    snap_terminals: bool = True  # Anschlüsse auf das Raster runden (sonst nur melden)


@dataclass
class QetGeometry:
    primitives: list[Primitive] = field(default_factory=list)
    width: int = 10
    height: int = 10
    hotspot_x: int = 0
    hotspot_y: int = 0
    scale: float = 1.0  # Pixel je Zeichnungseinheit
    off_grid_terminals: int = 0


def to_qet(drawing: Drawing, opts: Options | None = None) -> QetGeometry:
    opts = opts or Options()
    shapes = [p for p in drawing.primitives if not isinstance(p, Terminal)]
    terminals = [p for p in drawing.primitives if isinstance(p, Terminal)]
    bb = bbox(shapes) or bbox(terminals)
    if bb is None:
        raise EmptyDrawingError("Die Zeichnung enthält keine übertragbaren Objekte.")
    minx, miny, maxx, maxy = bb

    if opts.fit_px:
        extent = max(maxx - minx, maxy - miny)
        scale = opts.fit_px / extent if extent > 0 else 1.0
    else:
        scale = opts.px_per_mm * drawing.units_to_mm

    # Ursprung: erster Anschluss (damit er auf dem Raster liegt), sonst linke obere Ecke
    ox, oy = (terminals[0].x, terminals[0].y) if terminals else (minx, maxy)

    def pt(x: float, y: float) -> tuple[float, float]:
        return (x - ox) * scale, -(y - oy) * scale

    out: list[Primitive] = []
    for p in drawing.primitives:
        match p:
            case Line():
                x1, y1 = pt(p.x1, p.y1)
                x2, y2 = pt(p.x2, p.y2)
                out.append(Line(x1, y1, x2, y2, p.style))
            case Arc():
                cx, cy = pt(p.cx, p.cy)
                # Spiegeln an der x-Achse + Qt-Winkel (gegen den Uhrzeigersinn auf dem
                # Bildschirm) heben sich auf: Start und Spanne bleiben gleich.
                out.append(Arc(cx, cy, p.rx * scale, p.ry * scale, p.start, p.span, p.style))
            case Ellipse():
                cx, cy = pt(p.cx, p.cy)
                out.append(Ellipse(cx, cy, p.rx * scale, p.ry * scale, p.style))
            case Polyline():
                out.append(Polyline(tuple(pt(x, y) for x, y in p.points), p.closed, p.style))
            case Text():
                x, y = pt(p.x, p.y)
                out.append(Text(x, y, p.text, p.height * scale, p.rotation, p.style))
            case Terminal():
                x, y = pt(p.x, p.y)
                if opts.snap_terminals:
                    x, y = round(x / opts.grid) * opts.grid, round(y / opts.grid) * opts.grid
                orient = p.orientation or _side(p.x, p.y, minx, miny, maxx, maxy)
                out.append(Terminal(x, y, p.name, orient))

    geo = QetGeometry(primitives=out, scale=scale)
    g = opts.grid
    qminx, qminy = (minx - ox) * scale, -(maxy - oy) * scale
    qmaxx, qmaxy = (maxx - ox) * scale, -(miny - oy) * scale
    for t in out:
        if isinstance(t, Terminal):
            qminx, qminy = min(qminx, t.x), min(qminy, t.y)
            qmaxx, qmaxy = max(qmaxx, t.x), max(qmaxy, t.y)
            if abs(t.x / g - round(t.x / g)) > 0.01 or abs(t.y / g - round(t.y / g)) > 0.01:
                geo.off_grid_terminals += 1
    geo.hotspot_x = max(0, math.ceil(-qminx / g - 1e-9) * g)
    geo.hotspot_y = max(0, math.ceil(-qminy / g - 1e-9) * g)
    geo.width = max(g, math.ceil((qmaxx + geo.hotspot_x) / g - 1e-9) * g)
    geo.height = max(g, math.ceil((qmaxy + geo.hotspot_y) / g - 1e-9) * g)
    return geo


def _side(x: float, y: float, minx: float, miny: float, maxx: float, maxy: float) -> str:
    """Anschlussrichtung = nächstgelegene Seite der Zeichnung (im DXF-Raum, Y oben)."""
    dist = {"n": abs(maxy - y), "s": abs(y - miny), "w": abs(x - minx), "e": abs(maxx - x)}
    return min(dist, key=dist.get)
