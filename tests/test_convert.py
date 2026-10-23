from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from make_samples import make_all
from dxf2qet.convert import convert, prepare
from dxf2qet.geometry import Arc, Drawing, Line, Terminal, Text, bbox
from dxf2qet.qet_element import build_definition, num
from dxf2qet.qet_project import build_project, element_file_name
from dxf2qet.reader import read_dxf
from dxf2qet.transform import EmptyDrawingError, Options, to_qet


@pytest.fixture(scope="session")
def samples(tmp_path_factory) -> dict[str, Path]:
    return make_all(tmp_path_factory.mktemp("samples"))


def qt_arc_point(el: ET.Element, angle: float) -> tuple[float, float]:
    """Punkt eines QET-<arc> wie Qt::drawArc ihn zeichnet (Winkel gegen den Uhrzeigersinn, Y unten)."""
    x, y = float(el.get("x")), float(el.get("y"))
    w, h = float(el.get("width")), float(el.get("height"))
    t = math.radians(angle)
    return x + w / 2 + w / 2 * math.cos(t), y + h / 2 - h / 2 * math.sin(t)


def parts(geo, tag: str) -> list[ET.Element]:
    return build_definition(geo, "t").find("description").findall(tag)


def test_arcs_all_quadrants_keep_their_endpoints(samples):
    drawing = read_dxf(samples["arcs"])
    geo = to_qet(drawing, Options(px_per_mm=1))
    arcs_dxf = [p for p in drawing.primitives if isinstance(p, Arc)]
    arcs_xml = parts(geo, "arc")
    assert len(arcs_xml) == 4
    # Ursprung = linke obere Ecke der Zeichnung (Y gespiegelt)
    minx, _, _, maxy = bbox(drawing.primitives)
    for a, el in zip(arcs_dxf, arcs_xml):
        start, span = float(el.get("start")), float(el.get("angle"))
        for dxf_angle, qet_angle in ((a.start, start), (a.start + a.span, start + span)):
            ex = a.cx + a.rx * math.cos(math.radians(dxf_angle)) - minx
            ey = -(a.cy + a.ry * math.sin(math.radians(dxf_angle)) - maxy)
            qx, qy = qt_arc_point(el, qet_angle)
            assert qx == pytest.approx(ex, abs=0.01) and qy == pytest.approx(ey, abs=0.01)


def test_y_axis_is_flipped():
    d = Drawing(primitives=[Line(0, 0, 0, 10)])
    geo = to_qet(d, Options(px_per_mm=1))
    line = geo.primitives[0]
    # DXF-Punkt (0,10) ist oben -> QET y=0, (0,0) unten -> y=10
    assert (line.y1, line.y2) == (10, 0)


def test_bounding_rect_contains_everything_and_is_on_grid(samples):
    for name, path in samples.items():
        geo = prepare(path).geometry
        assert geo.width % 10 == 0 and geo.height % 10 == 0, name
        assert geo.hotspot_x % 10 == 0 and geo.hotspot_y % 10 == 0, name
        for el in build_definition(geo, name).find("description"):
            for k, v in el.attrib.items():
                if k[0] == "x" and k[1:].isdigit() or k == "x1" or k == "x2" or k == "x":
                    if el.tag not in ("text", "arc"):  # arc: x/y = Rechteck der vollen Ellipse
                        assert -geo.hotspot_x - 0.01 <= float(v) <= geo.width - geo.hotspot_x + 0.01, (name, el.tag, k, v)
                if k[0] == "y" and k[1:].isdigit() or k == "y":
                    if el.tag not in ("text", "arc"):  # arc: x/y = Rechteck der vollen Ellipse
                        assert -geo.hotspot_y - 0.01 <= float(v) <= geo.height - geo.hotspot_y + 0.01, (name, el.tag, k, v)


def test_units_inch_and_scale(samples):
    d = read_dxf(samples["symbol"])
    assert d.units_to_mm == 25.4
    geo = to_qet(d, Options(px_per_mm=1, snap_terminals=False))
    terms = [p for p in geo.primitives if isinstance(p, Terminal)]
    assert terms[0].y == 0
    assert terms[1].y == pytest.approx(1.2 * 25.4)
    assert geo.off_grid_terminals == 1


def test_terminals_snap_and_orientation(samples):
    geo = prepare(samples["symbol"]).geometry  # 2 px/mm -> 60,96 px Abstand
    terms = [p for p in geo.primitives if isinstance(p, Terminal)]
    assert [(t.x, t.y, t.orientation) for t in terms] == [(0, 0, "n"), (0, 60, "s")]
    assert geo.off_grid_terminals == 0


def test_blocks_are_exploded_with_transform(samples):
    d = read_dxf(samples["blocks"])
    lines = [p for p in d.primitives if isinstance(p, Line)]
    assert len(lines) == 6
    # zweite Referenz: 90° gedreht, Faktor 2 -> erste Linie (0,0)-(0,5) wird (30,0)-(20,0)
    assert any(math.isclose(l.x1, 30) and math.isclose(l.x2, 20, abs_tol=1e-9) for l in lines)
    texts = [p.text for p in d.primitives if isinstance(p, Text)]
    assert "-K2" in texts


def test_bulge_becomes_curve(samples):
    d = read_dxf(samples["bulge"])
    (poly,) = d.primitives
    assert poly.closed and len(poly.points) > 10
    # Halbkreis über (0,0)-(20,0), Bulge 1 = gegen den Uhrzeigersinn -> nach unten (y<0)
    assert min(y for _, y in poly.points) == pytest.approx(-10, abs=0.1)


def test_mixed_entities_and_skips(samples):
    d = read_dxf(samples["mixed"])
    assert d.counts.get("ELLIPSE") == 3 and d.counts.get("SPLINE") == 1
    assert d.skipped.get("POINT") == 1
    xml = build_definition(to_qet(d), "m").find("description")
    assert len(xml.findall("ellipse")) == 1  # nur die achsparallele volle Ellipse
    assert len(xml.findall("arc")) == 1
    assert any("filling:black" in p.get("style") for p in xml.findall("polygon"))
    # "normal" = 1 Einheit breit und in QET viel fetter als die Vorschau; "thin" = 1 px
    assert all("line-weight:thin" in p.get("style") for p in xml if p.get("style"))


def test_layer_filter(samples):
    d = read_dxf(samples["symbol"], layers={"STRICH"})
    assert len(d.primitives) == 1 and d.primitives[0].style.line == "dashed"


def test_colors(samples):
    d = read_dxf(samples["symbol"], layers={"STRICH"}, keep_colors=True)
    assert d.primitives[0].style.color == "red"


def test_empty_drawing_raises():
    with pytest.raises(EmptyDrawingError):
        to_qet(Drawing())


def test_text_rotation_and_anchor():
    d = Drawing(primitives=[Text(0, 0, "X", 7, 90)])
    geo = to_qet(d, Options(px_per_mm=1))
    (el,) = parts(geo, "text")
    assert el.get("rotation") == "270"
    t = geo.primitives[0]
    # nach oben laufender Text: Oberkante liegt links von der Grundlinie
    assert float(el.get("x")) < t.x and float(el.get("y")) == pytest.approx(t.y, abs=0.01)


def test_project_embeds_element(samples, tmp_path):
    result = convert(samples["symbol"], tmp_path, "both", name="Spule K1")
    elmt, qet = result.written
    assert elmt.name == "Spule K1.elmt" and qet.suffix == ".qet"
    root = ET.parse(qet).getroot()
    inst = root.find("diagram/elements/element")
    ref = inst.get("type")
    assert ref == "embed://import/dxf/spule_k1.elmt"
    emb = root.find("collection/category[@name='import']/category[@name='dxf']/element[@name='spule_k1.elmt']/definition")
    assert emb is not None
    assert len(inst.findall("terminals/terminal")) == len(emb.findall("description/terminal")) == 2
    diagram = root.find("diagram")
    assert int(diagram.get("height")) == int(diagram.get("rows")) * int(diagram.get("rowsize")) + 20
    ET.parse(elmt)  # wohlgeformt


def test_big_drawing_grows_sheet():
    d = Drawing(primitives=[Line(0, 0, 2000, 1000)])
    proj = build_project(to_qet(d, Options(px_per_mm=1)), "gross")
    diagram = proj.find("diagram")
    assert int(diagram.get("cols")) * 60 >= 2000 and int(diagram.get("rows")) * 80 >= 1000


def test_helpers():
    assert num(-0.001) == "0" and num(1.5) == "1.5" and num(2.0) == "2"
    assert element_file_name("Schütz K1 (neu)") == "schutz_k1_neu.elmt"
