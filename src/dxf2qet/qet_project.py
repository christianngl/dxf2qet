"""QET-Projekt (.qet) mit einem Blatt, auf dem die Zeichnung als eingebettetes Element liegt.

Aufbau abgeglichen mit examples/ArduinoLCD.qet und examples/Projet_vierge.qet
aus dem QElectroTech-Repository.
"""

from __future__ import annotations

import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from .geometry import Terminal
from .qet_element import ELEMENT_VERSION, _write, build_definition, new_uuid, num
from .transform import QetGeometry

COLSIZE = 60
ROWSIZE = 80
HEADER = 20  # Höhe/Breite der Spalten- und Zeilenbeschriftung des Rahmens
MIN_COLS = 17  # Standard-Blatt von QET
MIN_ROWS = 8
MARGIN = 40
TERMINAL_ORIENT = {"n": "0", "e": "1", "s": "2", "w": "3"}

CONDUCTOR_DEFAULTS = {
    "type": "multi", "num": "", "formula": "", "function": "", "tension_protocol": "",
    "conductor_color": "", "conductor_section": "", "cable": "", "bus": "",
    "condsize": "1", "numsize": "9", "displaytext": "0", "onetextperfolio": "0",
    "vertirotatetext": "0", "horizrotatetext": "0", "text_color": "#000000",
    "bicolor": "false", "color2": "#000000", "dash-size": "1",
    "horizontal-alignment": "AlignBottom", "vertical-alignment": "AlignRight",
}

IMPORT_NAMES = {"de": "Importierte Elemente", "en": "Imported elements", "fr": "Éléments importés"}


def element_file_name(name: str) -> str:
    """Dateiname für die eingebettete Sammlung: nur a-z, 0-9, _ und -."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_").lower()
    return (s or "dxf_import") + ".elmt"


def build_project(geo: QetGeometry, name: str, info: str = "") -> ET.Element:
    elmt = element_file_name(name)
    cols = max(MIN_COLS, math.ceil((geo.width + 2 * MARGIN) / COLSIZE))
    rows = max(MIN_ROWS, math.ceil((geo.height + 2 * MARGIN) / ROWSIZE))

    project = ET.Element("project", {"title": name, "version": ELEMENT_VERSION})
    ET.SubElement(project, "properties")

    newdiagrams = ET.SubElement(project, "newdiagrams")
    ET.SubElement(newdiagrams, "border", _border(17, MIN_ROWS))
    ET.SubElement(newdiagrams, "inset", _inset(""))
    ET.SubElement(newdiagrams, "conductors", CONDUCTOR_DEFAULTS)
    ET.SubElement(newdiagrams, "report", {"label": "%f-%l%c"})

    diagram = ET.SubElement(project, "diagram", {
        **_border(cols, rows),
        **_inset(name),
        "height": str(rows * ROWSIZE + HEADER),
        "order": "1",
        "version": ELEMENT_VERSION,
        "freezeNewElement": "false",
        "freezeNewConductor": "false",
    })
    ET.SubElement(diagram, "defaultconductor", CONDUCTOR_DEFAULTS)
    elements = ET.SubElement(diagram, "elements")
    # Hotspot so setzen, dass die linke obere Ecke des Elements MARGIN vom Rahmen entfernt
    # auf dem 10er-Raster liegt
    x = HEADER + MARGIN + geo.hotspot_x
    y = HEADER + MARGIN + geo.hotspot_y
    inst = ET.SubElement(elements, "element", {
        "type": f"embed://import/dxf/{elmt}",
        "x": str(x), "y": str(y), "z": "10", "orientation": "0",
        "uuid": new_uuid(), "prefix": "", "freezeLabel": "false",
    })
    terms = ET.SubElement(inst, "terminals")
    for i, t in enumerate(p for p in geo.primitives if isinstance(p, Terminal)):
        ET.SubElement(terms, "terminal", {
            "id": str(i), "x": num(t.x), "y": num(t.y),
            "orientation": TERMINAL_ORIENT.get(t.orientation, "0"),
            "name": t.name, "number": "", "nameHidden": "0",
        })
    ET.SubElement(inst, "inputs")
    ET.SubElement(diagram, "conductors")
    ET.SubElement(diagram, "inputs")

    collection = ET.SubElement(project, "collection")
    cat_import = ET.SubElement(collection, "category", {"name": "import"})
    _names(cat_import, IMPORT_NAMES)
    cat_dxf = ET.SubElement(cat_import, "category", {"name": "dxf"})
    _names(cat_dxf, {"de": "DXF-Import", "en": "DXF import"})
    el = ET.SubElement(cat_dxf, "element", {"name": elmt})
    el.append(build_definition(geo, name, info))
    return project


def write_project(geo: QetGeometry, path: str | Path, name: str, info: str = "") -> Path:
    path = Path(path)
    _write(build_project(geo, name, info), path)
    return path


def _border(cols: int, rows: int) -> dict[str, str]:
    return {
        "cols": str(cols), "colsize": str(COLSIZE), "displaycols": "true",
        "rows": str(rows), "rowsize": str(ROWSIZE), "displayrows": "true",
    }


def _inset(title: str) -> dict[str, str]:
    return {
        "title": title, "author": "dxf2qet", "date": date.today().strftime("%Y%m%d"),
        "filename": "", "folio": "%id/%total", "plant": "", "locmach": "",
        "indexrev": "", "version": "", "auto_page_num": "", "displayAt": "bottom",
    }


def _names(parent: ET.Element, names: dict[str, str]) -> None:
    el = ET.SubElement(parent, "names")
    for lang, text in names.items():
        ET.SubElement(el, "name", {"lang": lang}).text = text
