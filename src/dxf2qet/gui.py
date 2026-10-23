"""Kleine PySide6-Oberfläche: DXF wählen, Optionen setzen, Vorschau, umwandeln."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGraphicsScene, QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
    QSplitter, QVBoxLayout, QWidget,
)

from . import __version__
from .convert import Result, prepare, write
from .qet_element import build_definition
from .reader import DEFAULT_TERMINAL_LAYER, QET_COLORS, DxfReadError
from .transform import EmptyDrawingError, Options

QET_LINE_STYLES = {
    "normal": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine, "dashdotted": Qt.DashDotLine,
}


class Preview(QGraphicsView):
    """Zeichnet die erzeugte Element-Definition so, wie QET sie liest."""

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("white"))
        self.setMinimumSize(380, 300)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def show_message(self, text: str) -> None:
        s = self.scene()
        s.clear()
        item = s.addText(text)
        item.setDefaultTextColor(QColor("#777"))
        s.setSceneRect(item.boundingRect())
        self.resetTransform()

    def show_definition(self, definition) -> None:
        s = self.scene()
        s.clear()
        w, h = int(definition.get("width")), int(definition.get("height"))
        hx, hy = int(definition.get("hotspot_x")), int(definition.get("hotspot_y"))
        frame = QPen(QColor("#9ab"), 0, Qt.DashLine)
        s.addRect(-hx, -hy, w, h, frame)
        cross = QPen(QColor("#e33"), 0)
        s.addLine(-3, 0, 3, 0, cross)
        s.addLine(0, -3, 0, 3, cross)

        for el in definition.find("description"):
            pen, brush = _pen_brush(el.get("style", ""))
            f = lambda k: float(el.get(k, 0))  # noqa: E731
            match el.tag:
                case "line":
                    s.addLine(f("x1"), f("y1"), f("x2"), f("y2"), pen)
                case "ellipse":
                    s.addEllipse(f("x"), f("y"), f("width"), f("height"), pen, brush)
                case "arc":
                    path = QPainterPath()
                    path.arcMoveTo(f("x"), f("y"), f("width"), f("height"), f("start"))
                    path.arcTo(f("x"), f("y"), f("width"), f("height"), f("start"), f("angle"))
                    s.addPath(path, pen)
                case "polygon":
                    pts = []
                    i = 1
                    while el.get(f"x{i}") is not None:
                        pts.append((f(f"x{i}"), f(f"y{i}")))
                        i += 1
                    if not pts:
                        continue
                    path = QPainterPath()
                    path.moveTo(*pts[0])
                    for p in pts[1:]:
                        path.lineTo(*p)
                    if el.get("closed") == "true":
                        path.closeSubpath()
                    s.addPath(path, pen, brush)
                case "text":
                    family, size = (el.get("font", "Sans Serif,9").split(",") + ["9"])[:2]
                    font = QFont(family)
                    font.setPointSizeF(max(float(size), 0.5))
                    item = s.addSimpleText(el.get("text", ""), font)
                    item.setBrush(QColor(el.get("color", "#000000")))
                    item.setPos(f("x"), f("y"))
                    item.setRotation(f("rotation"))
                case "terminal":
                    x, y = f("x"), f("y")
                    tp = QPen(QColor("#d22"), 0)
                    s.addEllipse(x - 2, y - 2, 4, 4, tp, QBrush(QColor("#d22")))
                    dx, dy = {"n": (0, -8), "s": (0, 8), "e": (8, 0), "w": (-8, 0)}.get(el.get("orientation"), (0, 0))
                    s.addLine(x, y, x + dx, y + dy, tp)

        rect = s.itemsBoundingRect().adjusted(-10, -10, 10, 10)
        s.setSceneRect(rect)
        self.fitInView(rect, Qt.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.scene().items():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)


def _pen_brush(style: str) -> tuple[QPen, QBrush]:
    props = dict(p.split(":", 1) for p in style.split(";") if ":" in p)
    color = QColor(*QET_COLORS.get(props.get("color", "black"), (0, 0, 0)))
    pen = QPen(color, 1)
    pen.setCosmetic(True)
    pen.setStyle(QET_LINE_STYLES.get(props.get("line-style", "normal"), Qt.SolidLine))
    filling = props.get("filling", "none")
    brush = QBrush(QColor(*QET_COLORS[filling])) if filling in QET_COLORS else QBrush(Qt.NoBrush)
    return pen, brush


class MainWindow(QMainWindow):
    def __init__(self, initial: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"DXF → QElectroTech  ({__version__})")
        self.setAcceptDrops(True)
        self.settings = QSettings("dxf2qet", "dxf2qet")
        self.dxf: Path | None = None
        self.result: Result | None = None
        self._loading = False

        self.preview_timer = QTimer(self, singleShot=True, interval=250)
        self.preview_timer.timeout.connect(self.refresh)

        # --- Datei
        self.file_label = QLabel("DXF-Datei hierher ziehen oder „Öffnen…“ wählen")
        self.file_label.setWordWrap(True)
        open_btn = QPushButton("Öffnen…")
        open_btn.clicked.connect(self.choose_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(open_btn)

        # --- Optionen
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name des Elements")

        self.target_group = QButtonGroup(self)
        target_row = QHBoxLayout()
        for key, label in (("elmt", "Element (.elmt)"), ("qet", "Projekt (.qet)"), ("both", "beides")):
            rb = QRadioButton(label)
            rb.setProperty("target", key)
            self.target_group.addButton(rb)
            target_row.addWidget(rb)
            if key == self.settings.value("target", "both"):
                rb.setChecked(True)

        self.scale_spin = QDoubleSpinBox(decimals=3, minimum=0.001, maximum=1000, singleStep=0.5)
        self.scale_spin.setValue(float(self.settings.value("scale", 2.0)))
        self.scale_spin.setSuffix(" px/mm")
        self.fit_check = QCheckBox("einpassen auf")
        self.fit_check.setChecked(self.settings.value("fit", "false") == "true")
        self.fit_spin = QDoubleSpinBox(decimals=0, minimum=10, maximum=20000, singleStep=10)
        self.fit_spin.setValue(float(self.settings.value("fit_px", 200)))
        self.fit_spin.setSuffix(" px")
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.scale_spin)
        scale_row.addWidget(self.fit_check)
        scale_row.addWidget(self.fit_spin)
        scale_row.addStretch()

        self.colors_check = QCheckBox("DXF-Farben übernehmen (sonst schwarz)")
        self.colors_check.setChecked(self.settings.value("colors", "false") == "true")
        self.snap_check = QCheckBox("Anschlüsse auf 10-px-Raster runden")
        self.snap_check.setChecked(self.settings.value("snap", "true") == "true")

        self.terminal_combo = QComboBox(editable=True)
        self.terminal_combo.addItem(DEFAULT_TERMINAL_LAYER)
        self.terminal_combo.setToolTip("Punkte und Kreise auf diesem Layer werden zu QET-Anschlüssen")

        self.layer_list = QListWidget()
        self.layer_list.setMaximumHeight(140)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("neben der DXF-Datei")
        out_btn = QPushButton("…")
        out_btn.setFixedWidth(30)
        out_btn.clicked.connect(self.choose_out_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_btn)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Ziel:", target_row)
        form.addRow("Maßstab:", scale_row)
        form.addRow("", self.colors_check)
        form.addRow("", self.snap_check)
        form.addRow("Anschluss-Layer:", self.terminal_combo)
        form.addRow("Layer:", self.layer_list)
        form.addRow("Ausgabe:", out_row)
        options_box = QGroupBox("Optionen")
        options_box.setLayout(form)

        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(500)

        self.convert_btn = QPushButton("Umwandeln")
        self.convert_btn.setDefault(True)
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self.convert)
        self.open_dir_btn = QPushButton("Ordner öffnen")
        self.open_dir_btn.setEnabled(False)
        self.open_dir_btn.clicked.connect(self.open_out_dir)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.open_dir_btn)
        btn_row.addWidget(self.convert_btn)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addLayout(file_row)
        lv.addWidget(options_box)
        lv.addWidget(QLabel("Protokoll:"))
        lv.addWidget(self.log, 1)
        lv.addLayout(btn_row)

        self.preview = Preview()
        self.preview.show_message("Vorschau")
        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.resize(1100, 680)

        for sig in (self.scale_spin.valueChanged, self.fit_spin.valueChanged, self.fit_check.toggled,
                    self.colors_check.toggled, self.snap_check.toggled,
                    self.terminal_combo.currentTextChanged, self.layer_list.itemChanged):
            sig.connect(self.schedule_refresh)
        self.fit_check.toggled.connect(self._update_scale_widgets)
        self._update_scale_widgets()

        if initial:
            self.load(initial)

    # --- Datei laden ---------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if any(u.toLocalFile().lower().endswith(".dxf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".dxf"):
                self.load(u.toLocalFile())
                break

    def choose_file(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, "DXF öffnen", start, "DXF-Zeichnungen (*.dxf);;Alle Dateien (*)")
        if path:
            self.load(path)

    def choose_out_dir(self) -> None:
        start = self.out_edit.text() or (str(self.dxf.parent) if self.dxf else str(Path.home()))
        path = QFileDialog.getExistingDirectory(self, "Ausgabeordner", start)
        if path:
            self.out_edit.setText(path)

    def load(self, path: str) -> None:
        self.dxf = Path(path)
        self.settings.setValue("last_dir", str(self.dxf.parent))
        self.file_label.setText(str(self.dxf))
        self.name_edit.setText(self.dxf.stem)
        self.result = None
        self._loading = True
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.result = prepare(self.dxf, options=self.options(), keep_colors=self.colors_check.isChecked(),
                                      terminal_layer=self.terminal_combo.currentText())
            finally:
                QApplication.restoreOverrideCursor()
            self._fill_layers(self.result.drawing.layers)
            self._log(f"Geladen: {self.dxf.name}")
            self._show_result()
        except (DxfReadError, EmptyDrawingError) as exc:
            self._error(str(exc))
        except Exception:
            self._error("Unerwarteter Fehler beim Lesen:\n" + traceback.format_exc())
        finally:
            self._loading = False

    def _fill_layers(self, layers: list[str]) -> None:
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for name in layers:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.layer_list.addItem(item)
        self.layer_list.blockSignals(False)
        current = self.terminal_combo.currentText()
        self.terminal_combo.blockSignals(True)
        self.terminal_combo.clear()
        self.terminal_combo.addItems([DEFAULT_TERMINAL_LAYER] + [n for n in layers if n.upper() != DEFAULT_TERMINAL_LAYER])
        self.terminal_combo.setCurrentText(current)
        self.terminal_combo.blockSignals(False)

    # --- Vorschau ------------------------------------------------------

    def options(self) -> Options:
        return Options(
            px_per_mm=self.scale_spin.value(),
            fit_px=self.fit_spin.value() if self.fit_check.isChecked() else None,
            snap_terminals=self.snap_check.isChecked(),
        )

    def selected_layers(self) -> set[str] | None:
        items = [self.layer_list.item(i) for i in range(self.layer_list.count())]
        checked = {i.text() for i in items if i.checkState() == Qt.Checked}
        return None if len(checked) == len(items) else checked

    def _update_scale_widgets(self) -> None:
        self.fit_spin.setEnabled(self.fit_check.isChecked())
        self.scale_spin.setEnabled(not self.fit_check.isChecked())

    def schedule_refresh(self, *_args) -> None:
        if self.dxf and not self._loading:
            self.preview_timer.start()

    def refresh(self) -> None:
        if not self.dxf:
            return
        try:
            self.result = prepare(self.dxf, layers=self.selected_layers(), options=self.options(),
                                  terminal_layer=self.terminal_combo.currentText(),
                                  keep_colors=self.colors_check.isChecked())
            self._show_result()
        except EmptyDrawingError as exc:
            self.result = None
            self.convert_btn.setEnabled(False)
            self.preview.show_message(str(exc))
        except Exception:
            self.result = None
            self._error("Unerwarteter Fehler:\n" + traceback.format_exc())

    def _show_result(self) -> None:
        r = self.result
        self.preview.show_definition(build_definition(r.geometry, self.name_edit.text() or "vorschau"))
        self.convert_btn.setEnabled(True)
        g = r.geometry
        self.statusBar().showMessage(
            f"{len(r.drawing.primitives)} Objekte · Element {g.width} x {g.height} px · "
            f"Maßstab {g.scale:.4g} px/Einheit · Übersprungen: {sum(r.drawing.skipped.values())}"
        )

    # --- Umwandeln -----------------------------------------------------

    def target(self) -> str:
        btn = self.target_group.checkedButton()
        return btn.property("target") if btn else "both"

    def out_dir(self) -> Path:
        return Path(self.out_edit.text()) if self.out_edit.text().strip() else self.dxf.parent

    def convert(self) -> None:
        if not self.dxf:
            return
        self.preview_timer.stop()
        self.refresh()
        if not self.result:
            return
        name = self.name_edit.text().strip() or self.dxf.stem
        name = "".join("_" if c in '<>:"/\\|?*' else c for c in name)
        out_dir = self.out_dir()
        existing = [out_dir / f"{name}.{ext}" for ext in ("elmt", "qet") if self.target() in (ext, "both")]
        existing = [p for p in existing if p.exists()]
        if existing and QMessageBox.question(
            self, "Überschreiben?", "Diese Dateien gibt es schon:\n" + "\n".join(map(str, existing)) + "\n\nÜberschreiben?"
        ) != QMessageBox.Yes:
            return
        try:
            self.result.written.clear()
            write(self.result, out_dir, name, self.target(), self.dxf.name)
        except OSError as exc:
            self._error(f"Schreiben fehlgeschlagen: {exc}")
            return
        self._log("\n".join(self.result.report()) + "\n")
        self.open_dir_btn.setEnabled(True)
        self._save_settings()

    def open_out_dir(self) -> None:
        if self.dxf:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir())))

    # --- Sonstiges -----------------------------------------------------

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _error(self, text: str) -> None:
        self._log("FEHLER: " + text)
        self.preview.show_message("Fehler – siehe Protokoll")
        self.convert_btn.setEnabled(False)

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("target", self.target())
        s.setValue("scale", self.scale_spin.value())
        s.setValue("fit", "true" if self.fit_check.isChecked() else "false")
        s.setValue("fit_px", self.fit_spin.value())
        s.setValue("colors", "true" if self.colors_check.isChecked() else "false")
        s.setValue("snap", "true" if self.snap_check.isChecked() else "false")

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)


def run(initial: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("dxf2qet")
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))  # gepackt: Bundle-Ordner
    icon = base / "assets" / "icon.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(initial)
    win.show()
    if os.environ.get("DXF2QET_SCREENSHOT"):
        # für automatische Tests: Fenster nach dem Laden abfotografieren und beenden
        def snap() -> None:
            win.grab().save(os.environ["DXF2QET_SCREENSHOT"])
            app.quit()

        QTimer.singleShot(1500, snap)
    return app.exec()
