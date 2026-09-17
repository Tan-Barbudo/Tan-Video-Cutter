import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class TanVideoCutter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path: Path | None = None
        self.setWindowTitle("Tan Video Cutter")
        self.resize(760, 560)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("Tan Video Cutter")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("Limpia silencios, pausas y muletillas para editar más rápido.")
        subtitle.setStyleSheet("font-size: 14px; color: #666;")

        self.file_label = QLabel("Ningún video seleccionado")
        self.file_label.setWordWrap(True)
        choose = QPushButton("Seleccionar video")
        choose.clicked.connect(self.choose_video)

        file_row = QHBoxLayout()
        file_row.addWidget(choose)
        file_row.addWidget(self.file_label, 1)

        cleanup = QGroupBox("Limpieza")
        cleanup_layout = QVBoxLayout(cleanup)
        self.remove_silence = QCheckBox("Eliminar silencios")
        self.remove_silence.setChecked(True)
        self.reduce_pauses = QCheckBox("Reducir pausas largas")
        self.reduce_pauses.setChecked(True)
        self.fillers = QCheckBox("Detectar muletillas")
        self.fillers.setChecked(True)
        self.repetitions = QCheckBox("Detectar repeticiones")
        self.repetitions.setChecked(True)
        for item in (self.remove_silence, self.reduce_pauses, self.fillers, self.repetitions):
            cleanup_layout.addWidget(item)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Nivel de edición:"))
        self.mode = QComboBox()
        self.mode.addItems(["Natural", "Dinámico", "Shorts"])
        mode_row.addWidget(self.mode)
        mode_row.addStretch()

        self.analyze_button = QPushButton("Analizar video")
        self.analyze_button.setMinimumHeight(42)
        self.analyze_button.clicked.connect(self.analyze)

        self.progress = QProgressBar()
        self.progress.setValue(0)

        self.status = QLabel("Selecciona un video para comenzar.")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(file_row)
        layout.addWidget(cleanup)
        layout.addLayout(mode_row)
        layout.addWidget(self.analyze_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addStretch()

        self.setCentralWidget(root)

    def choose_video(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar video",
            "",
            "Videos (*.mp4 *.mov *.mkv *.avi);;Todos los archivos (*)",
        )
        if filename:
            self.video_path = Path(filename)
            self.file_label.setText(self.video_path.name)
            self.status.setText("Video listo para analizar.")

    def analyze(self):
        if not self.video_path:
            QMessageBox.information(self, "Tan Video Cutter", "Primero selecciona un video.")
            return

        # MVP UI: the processing pipeline is implemented in the next milestone.
        selected = []
        if self.remove_silence.isChecked():
            selected.append("silencios")
        if self.reduce_pauses.isChecked():
            selected.append("pausas")
        if self.fillers.isChecked():
            selected.append("muletillas")
        if self.repetitions.isChecked():
            selected.append("repeticiones")

        self.progress.setValue(10)
        self.status.setText(
            f"Preparado para analizar {self.video_path.name} en modo {self.mode.currentText()}: "
            + ", ".join(selected)
            + "."
        )
        QMessageBox.information(
            self,
            "Primera etapa lista",
            "La interfaz ya funciona. El siguiente paso conecta FFmpeg y Whisper para realizar el análisis real.",
        )


def main():
    app = QApplication(sys.argv)
    window = TanVideoCutter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
