"""Presentation controllers for character management windows."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QPushButton, QWidget

from eve_craft.app.config import AppConfig
from eve_craft.app.presentation.ui_loader import load_ui_widget


def _prepare_window(window: QWidget, *, config: AppConfig, parent: QWidget | None) -> None:
    if parent is not None:
        window.setParent(parent, window.windowFlags() | Qt.WindowType.Window)

    if config.paths.icon_file.exists():
        window.setWindowIcon(QIcon(str(config.paths.icon_file)))


def _show_window(window: QWidget) -> None:
    window.show()
    window.raise_()
    window.activateWindow()


class AddCharacterWindowController(QObject):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window = load_ui_widget(config.paths.add_character_ui)
        _prepare_window(self.window, config=config, parent=parent)

    def show(self) -> None:
        _show_window(self.window)

    def close(self) -> None:
        self.window.close()


class ManageAccountsWindowController(QObject):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.window = load_ui_widget(config.paths.manage_accounts_ui)
        _prepare_window(self.window, config=config, parent=parent)

        self._add_character_window: AddCharacterWindowController | None = None
        self._add_character_button = self._find_button("btnAddCharacter")
        self._close_button = self._find_button("btnClose")

        self._add_character_button.clicked.connect(self._open_add_character_window)
        self._close_button.clicked.connect(self.window.close)
        self.window.closeEvent = self._close_event

    def show(self) -> None:
        _show_window(self.window)

    def _open_add_character_window(self) -> None:
        if self._add_character_window is None:
            self._add_character_window = AddCharacterWindowController(
                config=self._config,
                parent=self.window,
            )

        self._add_character_window.show()

    def _close_event(self, event: QCloseEvent) -> None:
        if self._add_character_window is not None:
            self._add_character_window.close()

        event.accept()

    def _find_button(self, object_name: str) -> QPushButton:
        button = self.window.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in character management UI.")

        return button
