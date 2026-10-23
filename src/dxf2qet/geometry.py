"""Neutrale Zeichnungs-Primitive zwischen DXF-Leser und QET-Schreiber.

Koordinaten liegen entweder im DXF-Raum (Y nach oben, Zeichnungseinheiten)
oder - nach transform.to_qet() - im QET-Raum (Y nach unten, Pixel, relativ
zum Hotspot). Die Klassen selbst sind in beiden Räumen dieselben.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Style:
    line: str = "normal"  # normal | dashed | dotted | dashdotted
    color: str = "black"  # QET-Farbname
    filled: bool = False


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    style: Style = Style()


@dataclass(frozen=True)
class Arc:
    """Achsparalleler Ellipsen- oder Kreisbogen.

    Winkel in Grad, gegen den Uhrzeigersinn, so wie man sie sieht
    (im DXF-Raum mathematisch, im QET-Raum wie Qt::drawArc).
    Bei Ellipsen sind es Parameterwinkel - genau wie bei DXF und Qt.
    """

    cx: float
    cy: float
    rx: float
    ry: float
    start: float
    span: float
    style: Style = Style()


@dataclass(frozen=True)
class Ellipse:
    cx: float
    cy: float
    rx: float
    ry: float
    style: Style = Style()


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    closed: bool = False
    style: Style = Style()


@dataclass(frozen=True)
class Text:
    """Text mit Grundlinien-Anfang (x, y), Schrifthöhe und Drehung (Grad, CCW)."""

    x: float
    y: float
    text: str
    height: float
    rotation: float = 0.0
    style: Style = Style()


@dataclass(frozen=True)
class Terminal:
    x: float
    y: float
    name: str = ""
    orientation: str = ""  # n | e | s | w, leer = automatisch bestimmen


Primitive = Line | Arc | Ellipse | Polyline | Text | Terminal


@dataclass
class Drawing:
    primitives: list[Primitive] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)  # übernommene DXF-Typen
    skipped: dict[str, int] = field(default_factory=dict)  # nicht unterstützte DXF-Typen
    layers: list[str] = field(default_factory=list)
    units_to_mm: float = 1.0
    name: str = ""

    def count(self, kind: str, skipped: bool = False) -> None:
        target = self.skipped if skipped else self.counts
        target[kind] = target.get(kind, 0) + 1


def arc_point(a: Arc, angle_deg: float) -> tuple[float, float]:
    """Punkt auf dem Bogen im DXF-Raum (Y nach oben)."""
    t = math.radians(angle_deg)
    return a.cx + a.rx * math.cos(t), a.cy + a.ry * math.sin(t)


def points_of(p: Primitive) -> list[tuple[float, float]]:
    """Punkte, die die Ausdehnung eines Primitivs abdecken (für Bounding-Boxen)."""
    match p:
        case Line():
            return [(p.x1, p.y1), (p.x2, p.y2)]
        case Arc():
            n = max(2, int(abs(p.span) / 5) + 1)
            return [arc_point(p, p.start + p.span * i / (n - 1)) for i in range(n)]
        case Ellipse():
            return [(p.cx - p.rx, p.cy - p.ry), (p.cx + p.rx, p.cy + p.ry)]
        case Polyline():
            return list(p.points)
        case Text():
            # grobe Schätzung: Zeichenbreite ~ 0,6 x Höhe, Drehung ignoriert
            lines = p.text.split("\n")
            w = 0.6 * p.height * max(len(s) for s in lines)
            below = 1.67 * p.height * (len(lines) - 1)  # weitere Zeilen liegen darunter
            c, s = math.cos(math.radians(p.rotation)), math.sin(math.radians(p.rotation))
            corners = [(0, -below), (w, -below), (0, p.height), (w, p.height)]
            return [(p.x + x * c - y * s, p.y + x * s + y * c) for x, y in corners]
        case Terminal():
            return [(p.x, p.y)]
    return []


def bbox(prims: list[Primitive]) -> tuple[float, float, float, float] | None:
    pts = [pt for p in prims for pt in points_of(p)]
    if not pts:
        return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


__all__ = [
    "Arc", "Drawing", "Ellipse", "Line", "Polyline", "Primitive", "Style",
    "Terminal", "Text", "arc_point", "bbox", "points_of", "replace",
]
