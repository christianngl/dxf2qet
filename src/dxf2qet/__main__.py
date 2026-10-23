"""Ohne Argumente: GUI. Mit Argumenten: Kommandozeile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import TARGETS, convert
from .reader import DEFAULT_TERMINAL_LAYER, DxfReadError
from .transform import EmptyDrawingError, Options


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .gui import run

        return run()
    if len(argv) == 1 and not argv[0].startswith("-") and argv[0].lower().endswith(".dxf") and (getattr(sys, "frozen", False) or Path(sys.executable).stem.lower() == "pythonw"):
        # per Drag&Drop auf pythonw bzw. die gepackte .exe gestartet: GUI mit dieser Datei öffnen
        from .gui import run

        return run(argv[0])

    ap = argparse.ArgumentParser(prog="dxf2qet", description="DXF in QElectroTech-Element/-Projekt umwandeln")
    ap.add_argument("dxf", nargs="+", help="eine oder mehrere DXF-Dateien")
    ap.add_argument("--to", choices=TARGETS, default="both", help="Zielformat (Standard: both)")
    ap.add_argument("--out", help="Ausgabeordner (Standard: neben der DXF)")
    ap.add_argument("--name", help="Name des Elements (nur bei einer Datei)")
    ap.add_argument("--scale", type=float, default=2.0, help="Pixel je Millimeter (Standard 2)")
    ap.add_argument("--no-snap", action="store_true", help="Anschlüsse nicht aufs 10-px-Raster runden")
    ap.add_argument("--fit", type=float, help="größte Seite auf so viele Pixel einpassen")
    ap.add_argument("--layers", help="nur diese Layer, durch Komma getrennt")
    ap.add_argument("--terminal-layer", default=DEFAULT_TERMINAL_LAYER, help="Layer mit Anschlusspunkten")
    ap.add_argument("--colors", action="store_true", help="DXF-Farben übernehmen (sonst schwarz)")
    ap.add_argument("--gui", action="store_true", help="GUI mit der ersten Datei öffnen")
    args = ap.parse_args(argv)

    if args.gui:
        from .gui import run

        return run(args.dxf[0])

    layers = {s.strip() for s in args.layers.split(",")} if args.layers else None
    opts = Options(px_per_mm=args.scale, fit_px=args.fit, snap_terminals=not args.no_snap)
    rc = 0
    for path in args.dxf:
        print(f"== {path}")
        try:
            result = convert(path, args.out, args.to, args.name if len(args.dxf) == 1 else None,
                             layers=layers, options=opts, terminal_layer=args.terminal_layer,
                             keep_colors=args.colors)
        except (DxfReadError, EmptyDrawingError) as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            rc = 1
            continue
        for line in result.report():
            print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
