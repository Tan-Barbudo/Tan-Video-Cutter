import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QProgressBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView
)

from core import (
    Cut, detect_fillers, detect_repetitions, detect_silences, export_video,
    media_duration, merge_cuts, transcribe_words
)


class AnalysisWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(object, float)
    failed = Signal(str)

    def __init__(self, path: Path, mode: str, silence: bool, fillers: bool, repetitions: bool):
        super().__init__()
        self.path = path
        self.mode = mode
        self.use_silence = silence
        self.use_fillers = fillers
        self.use_repetitions = repetitions

    def run(self):
        try:
            cuts: list[Cut] = []
            duration = media_duration(self.path)
            self.progress.emit(10, "Leyendo video...")
            if self.use_silence:
                self.progress.emit(25, "Detectando silencios y pausas...")
                cuts.extend(detect_silences(self.path, self.mode))

            if self.use_fillers or self.use_repetitions:
                self.progress.emit(45, "Transcribiendo localmente con Whisper...")
                words = transcribe_words(self.path)
                if self.use_fillers:
                    self.progress.emit(70, "Buscando muletillas...")
                    cuts.extend(detect_fillers(words))
                if self.use_repetitions:
                    self.progress.emit(82, "Buscando repeticiones...")
                    cuts.extend(detect_repetitions(words))

            self.progress.emit(95, "Preparando resultados...")
            cuts = merge_cuts(cuts)
            self.finished_ok.emit(cuts, duration)
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, output: Path, cuts: list[Cut]):
        super().__init__()
        self.source = source
        self.output = output
        self.cuts = cuts

    def run(self):
        try:
            self.progress.emit("Exportando video. Puede tardar varios minutos...")
            export_video(self.source, self.output, self.cuts)
            self.finished_ok.emit(str(self.output))
        except Exception as exc:
            self.failed.emit(str(exc))


class TanVideoCutter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path: Path | None = None
        self.cuts: list[Cut] = []
        self.duration = 0.0
        self.worker = None
        self.setWindowTitle("Tan Video Cutter")
        self.resize(900, 720)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(12)

        title = QLabel("Tan Video Cutter")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("Limpia silencios, pausas, muletillas y repeticiones sin subir tus videos.")
        subtitle.setStyleSheet("color: #666;")

        choose = QPushButton("Seleccionar video")
        choose.clicked.connect(self.choose_video)
        self.file_label = QLabel("Ningún video seleccionado")
        file_row = QHBoxLayout(); file_row.addWidget(choose); file_row.addWidget(self.file_label, 1)

        cleanup = QGroupBox("Qué quieres limpiar")
        clean = QHBoxLayout(cleanup)
        self.remove_silence = QCheckBox("Silencios / pausas"); self.remove_silence.setChecked(True)
        self.fillers = QCheckBox("Muletillas"); self.fillers.setChecked(True)
        self.repetitions = QCheckBox("Repeticiones"); self.repetitions.setChecked(True)
        clean.addWidget(self.remove_silence); clean.addWidget(self.fillers); clean.addWidget(self.repetitions); clean.addStretch()

        mode_row = QHBoxLayout(); mode_row.addWidget(QLabel("Estilo:"))
        self.mode = QComboBox(); self.mode.addItems(["Natural", "Dinámico", "Shorts"])
        mode_row.addWidget(self.mode); mode_row.addStretch()

        self.analyze_button = QPushButton("Analizar video")
        self.analyze_button.setMinimumHeight(40); self.analyze_button.clicked.connect(self.analyze)
        self.progress = QProgressBar(); self.progress.setValue(0)
        self.status = QLabel("Selecciona un video para comenzar.")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Quitar", "Desde", "Hasta", "Tipo", "Detalle"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(260)

        self.summary = QLabel("Todavía no hay análisis.")
        self.export_button = QPushButton("Exportar MP4 limpio")
        self.export_button.setMinimumHeight(40); self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)

        layout.addWidget(title); layout.addWidget(subtitle); layout.addLayout(file_row)
        layout.addWidget(cleanup); layout.addLayout(mode_row); layout.addWidget(self.analyze_button)
        layout.addWidget(self.progress); layout.addWidget(self.status); layout.addWidget(self.table)
        layout.addWidget(self.summary); layout.addWidget(self.export_button)
        self.setCentralWidget(root)

    def choose_video(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Seleccionar video", "", "Videos (*.mp4 *.mov *.mkv *.avi);;Todos (*)")
        if filename:
            self.video_path = Path(filename); self.file_label.setText(self.video_path.name)
            self.status.setText("Video listo para analizar."); self.export_button.setEnabled(False)

    def analyze(self):
        if not self.video_path:
            QMessageBox.information(self, "Tan Video Cutter", "Primero selecciona un video."); return
        self.analyze_button.setEnabled(False); self.export_button.setEnabled(False); self.table.setRowCount(0)
        self.worker = AnalysisWorker(self.video_path, self.mode.currentText(), self.remove_silence.isChecked(), self.fillers.isChecked(), self.repetitions.isChecked())
        self.worker.progress.connect(self.on_progress); self.worker.finished_ok.connect(self.analysis_done); self.worker.failed.connect(self.failed)
        self.worker.start()

    def on_progress(self, value, text):
        self.progress.setValue(value); self.status.setText(text)

    def analysis_done(self, cuts, duration):
        self.cuts = cuts; self.duration = duration
        self.table.setRowCount(len(cuts))
        for row, cut in enumerate(cuts):
            check = QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(self.fmt(cut.start)))
            self.table.setItem(row, 2, QTableWidgetItem(self.fmt(cut.end)))
            self.table.setItem(row, 3, QTableWidgetItem(cut.kind))
            self.table.setItem(row, 4, QTableWidgetItem(cut.label))
        removed = sum(c.duration for c in cuts)
        self.summary.setText(f"Original: {self.fmt(duration)}   |   Cortes sugeridos: {len(cuts)}   |   Tiempo a quitar aprox.: {self.fmt(removed)}   |   Final aprox.: {self.fmt(max(0, duration-removed))}")
        self.progress.setValue(100); self.status.setText("Análisis terminado. Desmarca cualquier corte que quieras conservar.")
        self.analyze_button.setEnabled(True); self.export_button.setEnabled(True)

    def failed(self, message):
        self.analyze_button.setEnabled(True); self.export_button.setEnabled(bool(self.cuts)); self.progress.setValue(0)
        self.status.setText("Se produjo un error."); QMessageBox.critical(self, "Error", message)

    def export(self):
        if not self.video_path: return
        for row, cut in enumerate(self.cuts):
            item = self.table.item(row, 0); cut.enabled = bool(item and item.checkState() == Qt.CheckState.Checked)
        default = self.video_path.with_name(self.video_path.stem + "_limpio.mp4")
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar video", str(default), "MP4 (*.mp4)")
        if not filename: return
        self.export_button.setEnabled(False)
        self.worker = ExportWorker(self.video_path, Path(filename), self.cuts)
        self.worker.progress.connect(self.status.setText); self.worker.finished_ok.connect(self.export_done); self.worker.failed.connect(self.failed)
        self.worker.start()

    def export_done(self, filename):
        self.export_button.setEnabled(True); self.status.setText("Exportación terminada.")
        QMessageBox.information(self, "Listo", f"Video guardado en:\n{filename}")

    @staticmethod
    def fmt(seconds):
        seconds = max(0, int(round(seconds))); return f"{seconds//60:02d}:{seconds%60:02d}"


def main():
    app = QApplication(sys.argv); window = TanVideoCutter(); window.show(); sys.exit(app.exec())


if __name__ == "__main__": main()
