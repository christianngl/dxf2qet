"""Gemeinsamer Ablauf für GUI und Kommandozeile."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .geometry import Drawing
from .qet_element import write_element
from .qet_project import write_project
from .reader import DEFAULT_TERMINAL_LAYER, read_dxf
from .transform import Options, QetGeometry, to_qet

TARGETS = ("elmt", "qet", "both")


@dataclass
class Result:
    drawing: Drawing
    geometry: QetGeometry
    written: list[Path] = field(default_factory=list)

    def report(self) -> list[str]:
        d, g = self.drawing, self.geometry
        lines = [f"Übernommen: {_fmt(d.counts) or 'nichts'}"]
        if d.skipped:
            lines.append(f"Übersprungen: {_fmt(d.skipped)}")
        lines.append(f"Elementgröße: {g.width} x {g.height} px (Maßstab {g.scale:.4g} px je Einheit)")
        if g.off_grid_terminals:
            lines.append(f"Hinweis: {g.off_grid_terminals} Anschluss/Anschlüsse liegen nicht auf dem 10-px-Raster.")
        lines += [f"Geschrieben: {p}" for p in self.written]
        return lines


def _fmt(counts: dict[str, int]) -> str:
    return ", ".join(f"{n}x {k}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def prepare(
    dxf: str | Path,
    layers: set[str] | None = None,
    options: Options | None = None,
    terminal_layer: str = DEFAULT_TERMINAL_LAYER,
    keep_colors: bool = False,
) -> Result:
    drawing = read_dxf(dxf, layers=layers, terminal_layer=terminal_layer, keep_colors=keep_colors)
    return Result(drawing, to_qet(drawing, options))


def write(result: Result, out_dir: str | Path, name: str, target: str = "both", source: str = "") -> Result:
    if target not in TARGETS:
        raise ValueError(f"Unbekanntes Ziel: {target}")
    out_dir = Path(out_dir)
    info = f"Importiert aus {source} mit dxf2qet" if source else "Importiert mit dxf2qet"
    if target in ("elmt", "both"):
        result.written.append(write_element(result.geometry, out_dir / f"{name}.elmt", name, info))
    if target in ("qet", "both"):
        result.written.append(write_project(result.geometry, out_dir / f"{name}.qet", name, info))
    return result


def convert(dxf: str | Path, out_dir: str | Path | None = None, target: str = "both",
            name: str | None = None, **kwargs) -> Result:
    dxf = Path(dxf)
    result = prepare(dxf, **kwargs)
    return write(result, out_dir or dxf.parent, name or dxf.stem, target, dxf.name)
