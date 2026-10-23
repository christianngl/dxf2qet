# AGENTS.md – Übergabe-Log dxf2qet

## Ziel
DXF → QElectroTech (.elmt Element und/oder .qet Projekt), kleine PySide6-GUI, CLI für Tests.
Plan: ~/.claude/plans/baue-einen-konverter-der-hashed-rocket.md

## Stand
- [x] reader / transform / qet_element / qet_project / convert / CLI
- [x] Tests (pytest, Beispiel-DXFs aus tests/make_samples.py)
- [x] GUI mit Vorschau, Layer-Filter, Optionen (QSettings)
- [x] start.ps1, Desktop-Verknüpfung „DXF zu QElectroTech“ (pythonw -m dxf2qet, Icon assets/icon.ico), cockpit.ini
- [x] Eigenständiges Paket: build.ps1 (PyInstaller, --windowed) -> dist\dxf2qet-<version>-win64.zip, Kopie auf dem Desktop
- [ ] Sichtprüfung in echtem QElectroTech (ist auf diesem PC nicht installiert)

## Wissen / Stolpersteine
- uv liegt unter %LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_…\uv.exe (nicht im PATH der Tool-Shell).
- QET-Format geprüft gegen qelectrotech-source-mirror: examples/*.qet, sources/editor/graphicspart/*.cpp.
- Bogenwinkel: QET nimmt Qt::drawArc-Winkel (sichtbar gegen den Uhrzeigersinn, Y unten). Nach dem
  Y-Spiegeln bleiben DXF-Start und -Spanne daher UNVERÄNDERT (Test test_arcs_all_quadrants...).
- Element-Koordinaten sind relativ zum Hotspot; width/height/hotspot auf 10 gerundet.
- Statischer <text>: x/y = linke obere Ecke (ohne Dokument-Rand); DXF-Text ist auf der Grundlinie verankert
  -> Umrechnung in qet_element._text (Schätzwerte für Oberlänge/Schriftgröße).
- Diagramm-Attribut height = rows*rowsize + 20.
- pythonw + genau eine .dxf als Argument (Drag&Drop auf Verknüpfung) -> GUI statt CLI.
- Gepackte .exe: Drag&Drop-Erkennung über sys.frozen, Icon über sys._MEIPASS. Die .exe hat keine Konsole,
  CLI-Ausgaben gibt es nur in der Quellversion (start.ps1).
- build.ps1 ohne ErrorActionPreference=Stop (PS 5.1 wertet uv-stderr sonst als Fehler).
- Linienstärke: line-weight "thin" (Qt-Stiftbreite 0 = kosmetisch 1 px). "normal" = 1,0 Einheiten, wächst mit dem
  Zoom und sah in QET mehr als doppelt so fett aus wie die Vorschau. Vorschau wertet line-weight wie QET aus.
- GUI-Screenshot für Tests: Umgebungsvariable DXF2QET_SCREENSHOT=<png> setzen, Fenster schließt nach 1,5 s.

## Log
- 2026-10-22: Erstversion gebaut, 15 Tests grün, GUI-Screenshots geprüft.
- 2026-10-22: Standalone-ZIP (67 MB) gebaut, entpackt in leerem Ordner getestet, auf Desktop kopiert.
