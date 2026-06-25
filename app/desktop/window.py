from __future__ import annotations

import socket
import threading

import uvicorn

from app.compatibility.validator import validate_platform
from app.log_config.setup import configure_logging
from app.main import app
from app.recovery.manager import ensure_runtime_files
from app.validation.startup import validate_runtime


def _qt_imports():
    # Lazy import keeps server/test environments functional without GUI libs at import time.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

    return Qt, QApplication, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return False
    except (ConnectionRefusedError, OSError):
        return True


def run_desktop() -> int:
    Qt, QApplication, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget = _qt_imports()

    class DesktopController(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.logger = configure_logging()
            self.setWindowTitle("LabLink Core Desktop")
            self.resize(700, 420)

            self.status = QLabel("Initializing...")
            self.status.setAlignment(Qt.AlignCenter)
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.start_btn = QPushButton("Start API Service")
            self.start_btn.clicked.connect(self.start_server)

            layout = QVBoxLayout()
            layout.addWidget(self.status)
            layout.addWidget(self.start_btn)
            layout.addWidget(self.log_view)
            self.setLayout(layout)

            self._server_thread: threading.Thread | None = None
            self._run_startup_checks()

        def _log(self, msg: str) -> None:
            self.log_view.append(msg)
            self.logger.info(msg)

        def _run_startup_checks(self) -> None:
            report = ensure_runtime_files()
            for item in report.repaired:
                self._log(f"REPAIRED: {item}")
            for item in report.warnings:
                self._log(f"WARNING: {item}")

            runtime = validate_runtime()
            compatibility = validate_platform()
            self._log(f"Compatibility: {compatibility.details}")
            if runtime.ok:
                self.status.setText("Ready")
                self._log("Startup validation passed")
            else:
                self.status.setText("Validation Failed")
                for err in runtime.errors:
                    self._log(f"ERROR: {err}")

        def start_server(self) -> None:
            if self._server_thread and self._server_thread.is_alive():
                self._log("API service already running")
                return

            host, port = "127.0.0.1", 8000
            if not _is_port_available(host, port):
                self._log(f"Port {port} is already in use. Please stop the other process or use a different port.")
                self.status.setText("Port Conflict")
                return

            self._server_thread = threading.Thread(target=self._serve, daemon=True)
            self._server_thread.start()
            self.status.setText(f"API Service Running on http://{host}:{port}")
            self._log(f"Started API service on {host}:{port}")

        def _serve(self) -> None:
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    qapp = QApplication([])
    window = DesktopController()
    window.show()
    return qapp.exec()
