"""Screenshot des Hauptfensters mit einer Beispiel-DXF für die README.

Aufruf:  uv run python tools/screenshot.py <zeichnung.dxf> docs/screenshots/hauptfenster.png

Beispielzeichnungen erzeugt tests/make_samples.py. Die eigenen Einstellungen (zuletzt benutzter Ordner,
Optionen) werden dabei weder gelesen noch geändert, sie liegen nur in einer temporären INI-Datei.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QSettings  # noqa: E402

from dxf2qet import gui  # noqa: E402


def main(dxf: str, out: str) -> int:
    ini = Path(tempfile.mkdtemp()) / "dxf2qet.ini"
    gui.QSettings = lambda *_args: QSettings(str(ini), QSettings.IniFormat)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    os.environ["DXF2QET_SCREENSHOT"] = str(Path(out).resolve())
    return gui.run(dxf)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
