"""Erzeugt Test-DXFs mit ezdxf: python tests/make_samples.py [zielordner]"""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment


def basic(path: Path) -> None:
    doc = ezdxf.new(units=4)  # mm
    msp = doc.modelspace()
    msp.add_line((0, 0), (40, 0))
    msp.add_line((0, 0), (0, 20))
    msp.add_circle((20, 10), 5)
    msp.add_arc((20, 10), 8, 0, 90)
    msp.add_lwpolyline([(30, 5), (35, 15), (40, 5)], close=True)
    msp.add_text("K1", height=3.5).set_placement((2, 2))
    doc.saveas(path)


def arcs(path: Path) -> None:
    """Viertelbögen in allen vier Quadranten."""
    doc = ezdxf.new(units=4)
    msp = doc.modelspace()
    for i, start in enumerate((0, 90, 180, 270)):
        msp.add_arc((i * 30, 0), 10, start, start + 90)
    doc.saveas(path)


def bulge(path: Path) -> None:
    doc = ezdxf.new(units=4)
    msp = doc.modelspace()
    # Halbkreis-Bulge (1.0) zwischen den ersten beiden Punkten
    msp.add_lwpolyline([(0, 0, 0, 0, 1.0), (20, 0, 0, 0, 0), (20, -10), (0, -10)], format="xyseb", close=True)
    doc.saveas(path)


def blocks(path: Path) -> None:
    doc = ezdxf.new(units=4)
    blk = doc.blocks.new("KONTAKT")
    blk.add_line((0, 0), (0, 5))
    blk.add_line((0, 5), (3, 12))
    blk.add_line((0, 15), (0, 20))
    blk.add_attdef("BMK", (2, 8), dxfattribs={"height": 2.5})
    msp = doc.modelspace()
    msp.add_blockref("KONTAKT", (0, 0))
    ref = msp.add_blockref("KONTAKT", (30, 0), dxfattribs={"xscale": 2, "yscale": 2, "rotation": 90})
    ref.add_attrib("BMK", "-K2", (32, 8))
    doc.saveas(path)


def symbol(path: Path) -> None:
    """Schaltzeichen Spule mit zwei Anschlüssen auf dem Layer TERMINALS, in Zoll."""
    doc = ezdxf.new(units=1)
    doc.layers.add("TERMINALS")
    doc.layers.add("STRICH", linetype="DASHED", color=1)
    msp = doc.modelspace()
    msp.add_lwpolyline([(-0.3, -0.2), (0.3, -0.2), (0.3, 0.2), (-0.3, 0.2)], close=True)
    msp.add_line((0, 0.2), (0, 0.6))
    msp.add_line((0, -0.2), (0, -0.6))
    msp.add_line((0.5, -0.4), (0.5, 0.4), dxfattribs={"layer": "STRICH"})
    msp.add_point((0, 0.6), dxfattribs={"layer": "TERMINALS"})
    msp.add_point((0, -0.6), dxfattribs={"layer": "TERMINALS"})
    msp.add_mtext("A1", dxfattribs={"char_height": 0.1, "insert": (0.05, 0.55), "attachment_point": 7})
    t = msp.add_text("Q", height=0.12)
    t.set_placement((0, 0), align=TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(path)


def mixed(path: Path) -> None:
    doc = ezdxf.new(units=4)
    msp = doc.modelspace()
    msp.add_ellipse((0, 0), major_axis=(10, 0), ratio=0.5)
    msp.add_ellipse((30, 0), major_axis=(0, 10), ratio=0.5, start_param=0, end_param=3.14159)
    msp.add_ellipse((60, 0), major_axis=(7, 7), ratio=0.4)  # schräg -> Polylinie
    msp.add_spline([(0, 20), (10, 30), (20, 20), (30, 30)])
    msp.add_solid([(40, 20), (50, 20), (40, 30), (50, 30)])
    h = msp.add_hatch(color=2)
    h.paths.add_polyline_path([(60, 20), (70, 20), (70, 30)], is_closed=True)
    msp.add_point((5, 5))
    msp.add_mesh()
    doc.saveas(path)


SAMPLES = {"basic": basic, "arcs": arcs, "bulge": bulge, "blocks": blocks, "symbol": symbol, "mixed": mixed}


def make_all(target: Path) -> dict[str, Path]:
    target.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in SAMPLES.items():
        out[name] = target / f"{name}.dxf"
        fn(out[name])
    return out


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "samples"
    for p in make_all(dest).values():
        print(p)
