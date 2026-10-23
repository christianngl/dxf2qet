"""QET-Element (.elmt) aus QET-Geometrie erzeugen.

Format abgeglichen mit QElectroTech-Quellen (sources/editor/graphicspart/*.cpp)
und den Elementen in examples/*.qet.
"""

from __future__ import annotations

import math
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .geometry import Arc, Ellipse, Line, Polyline, Style, Terminal, Text
from .reader import QET_COLORS
from .transform import QetGeometry

ELEMENT_VERSION = "0.80"
FONT_FAMILY = "Sans Serif"
# Verhältnis Versalhöhe (DXF-Texthöhe) zu Schriftgröße in Pixeln bzw. Oberlänge
CAP_TO_EM = 1 / 0.7
ASCENT_TO_EM = 0.95


def num(v: float) -> str:
    """Zahl wie QET sie schreibt: höchstens 2 Nachkommastellen, ohne Nullen am Ende."""
    r = round(v, 2)
    if r == 0:
        r = 0.0  # kein "-0"
    return f"{r:.2f}".rstrip("0").rstrip(".")


def style_attr(s: Style) -> str:
    # "thin" = kosmetischer 1-px-Stift; "normal" wäre 1 Einheit breit und wirkt in QET (Zoom) sehr fett
    filling = s.color if s.filled else "none"
    return f"line-style:{s.line};line-weight:thin;filling:{filling};color:{s.color}"


def new_uuid() -> str:
    return "{" + str(uuid.uuid4()) + "}"


def build_definition(geo: QetGeometry, name: str, info: str = "", names: dict[str, str] | None = None) -> ET.Element:
    root = ET.Element("definition", {
        "type": "element",
        "version": ELEMENT_VERSION,
        "link_type": "simple",
        "width": str(geo.width),
        "height": str(geo.height),
        "hotspot_x": str(geo.hotspot_x),
        "hotspot_y": str(geo.hotspot_y),
    })
    ET.SubElement(root, "uuid", {"uuid": new_uuid()})
    names_el = ET.SubElement(root, "names")
    for lang, text in (names or {"de": name, "en": name}).items():
        ET.SubElement(names_el, "name", {"lang": lang}).text = text
    ET.SubElement(root, "informations").text = info
    desc = ET.SubElement(root, "description")
    for p in geo.primitives:
        el = _part(p)
        if el is not None:
            desc.append(el)
    return root


def _part(p) -> ET.Element | None:
    match p:
        case Line():
            return _line(p.x1, p.y1, p.x2, p.y2, p.style)
        case Arc():
            return ET.Element("arc", {
                "x": num(p.cx - p.rx), "y": num(p.cy - p.ry),
                "width": num(2 * p.rx), "height": num(2 * p.ry),
                "start": num(p.start), "angle": num(p.span),
                "style": style_attr(p.style), "antialias": "true",
            })
        case Ellipse():
            return ET.Element("ellipse", {
                "x": num(p.cx - p.rx), "y": num(p.cy - p.ry),
                "width": num(2 * p.rx), "height": num(2 * p.ry),
                "style": style_attr(p.style), "antialias": "true",
            })
        case Polyline():
            if len(p.points) == 2 and not p.closed:
                (x1, y1), (x2, y2) = p.points
                return _line(x1, y1, x2, y2, p.style)
            attrs = {}
            for i, (x, y) in enumerate(p.points, 1):
                attrs[f"x{i}"] = num(x)
                attrs[f"y{i}"] = num(y)
            attrs["closed"] = "true" if p.closed else "false"
            attrs["style"] = style_attr(p.style)
            attrs["antialias"] = "false"
            return ET.Element("polygon", attrs)
        case Text():
            return _text(p)
        case Terminal():
            return ET.Element("terminal", {
                "uuid": new_uuid(), "name": p.name,
                "x": num(p.x), "y": num(p.y),
                "orientation": p.orientation or "n", "type": "Generic",
            })
    return None


def _line(x1, y1, x2, y2, style: Style) -> ET.Element:
    return ET.Element("line", {
        "x1": num(x1), "y1": num(y1), "x2": num(x2), "y2": num(y2),
        "end1": "none", "end2": "none", "length1": "1.5", "length2": "1.5",
        "style": style_attr(style), "antialias": "false",
    })


def _text(p: Text) -> ET.Element:
    # QET verankert statische Texte oben links, DXF auf der Grundlinie.
    em_px = max(p.height * CAP_TO_EM, 1.0)
    point_size = max(round(em_px * 0.75, 1), 1.0)  # 96 dpi: 1 pt = 4/3 px
    ascent = em_px * ASCENT_TO_EM
    q = -p.rotation  # Qt dreht im Uhrzeigersinn
    qr = math.radians(q)
    x = p.x + ascent * math.sin(qr)
    y = p.y - ascent * math.cos(qr)
    r, g, b = QET_COLORS.get(p.style.color, (0, 0, 0))
    return ET.Element("text", {
        "x": num(x), "y": num(y), "text": p.text,
        "font": f"{FONT_FAMILY},{point_size:g},-1,5,50,0,0,0,0,0",
        "rotation": num(q % 360), "color": f"#{r:02x}{g:02x}{b:02x}",
        "uuid": new_uuid(),
    })


def write_element(geo: QetGeometry, path: str | Path, name: str, info: str = "") -> Path:
    path = Path(path)
    root = build_definition(geo, name, info)
    _write(root, path)
    return path


def _write(root: ET.Element, path: Path) -> None:
    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="UTF-8", xml_declaration=True)
