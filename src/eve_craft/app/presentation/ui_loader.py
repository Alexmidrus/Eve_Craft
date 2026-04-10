from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFile, QFileInfo, QIODevice
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QDialog, QMainWindow, QWidget


def load_ui_widget(ui_path: Path) -> QWidget:
    if not ui_path.exists():
        raise FileNotFoundError(f"UI file was not found: {ui_path}")

    loader = QUiLoader()
    loader.setWorkingDirectory(QFileInfo(str(ui_path)).dir())

    ui_file = QFile(str(ui_path))
    if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(f"Unable to open UI file: {ui_path}")

    try:
        widget = loader.load(ui_file)
    finally:
        ui_file.close()

    if widget is None:
        raise RuntimeError(f"Unable to load UI file: {ui_path}")

    return widget


def load_main_window(ui_path: Path) -> QMainWindow:
    widget = load_ui_widget(ui_path)
    if not isinstance(widget, QMainWindow):
        raise RuntimeError(f"UI file does not describe a QMainWindow: {ui_path}")

    return widget


def load_dialog(ui_path: Path) -> QDialog:
    widget = load_ui_widget(ui_path)
    if not isinstance(widget, QDialog):
        raise RuntimeError(f"UI file does not describe a QDialog: {ui_path}")

    return widget
