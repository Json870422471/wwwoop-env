from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.config import TOPBAR_HEIGHT, NAV_ITEMS
from src.core.i18n import get_translator

NAV_I18N_KEYS = ["nav.home", "nav.mysql", "nav.redis", "nav.java", "nav.php", "nav.python", "nav.node"]


class TopBarButton(QPushButton):
    def __init__(self, text: str, item_id: str, parent=None):
        super().__init__(text, parent)
        self.item_id = item_id
        self._active = False
        self.setFixedHeight(24)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        self._update_style()

    def _update_style(self):
        if self._active:
            fw = "bold"
            fg = "#000000"
        else:
            fw = "normal"
            fg = "#555555"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {fg};
                border: none;
                border-bottom: 2px solid {'#0078D4' if self._active else 'transparent'};
                padding: 2px 8px;
                font-size: 12px;
                font-weight: {fw};
            }}
            QPushButton:hover {{
                color: #000000;
            }}
            """
        )


class TopBar(QWidget):
    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TOPBAR_HEIGHT)
        self._buttons: dict[str, TopBarButton] = {}
        self._lang_btn: QPushButton | None = None
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        tr = get_translator()
        for idx, (item_id, _) in enumerate(NAV_ITEMS):
            btn = TopBarButton(tr.t(NAV_I18N_KEYS[idx]), item_id)
            btn.clicked.connect(lambda checked, iid=item_id: self._on_nav(iid))
            self._buttons[item_id] = btn
            layout.addWidget(btn)

        layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

        self._lang_btn = QPushButton(tr.switch_label)
        self._lang_btn.setFixedSize(40, 22)
        self._lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lang_btn.setFont(QFont("Microsoft YaHei", 8))
        self._lang_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #0078D4;
                border: 1px solid #0078D4;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0078D4;
                color: white;
            }
            """
        )
        self._lang_btn.clicked.connect(self._on_lang_toggle)
        layout.addWidget(self._lang_btn)

        self._buttons[NAV_ITEMS[0][0]].active = True

    def _on_language_changed(self):
        tr = get_translator()
        for idx, (item_id, _) in enumerate(NAV_ITEMS):
            self._buttons[item_id].setText(tr.t(NAV_I18N_KEYS[idx]))
        self._lang_btn.setText(tr.switch_label)

    def _on_lang_toggle(self):
        get_translator().toggle()

    def _on_nav(self, item_id: str):
        for btn in self._buttons.values():
            btn.active = False
        self._buttons[item_id].active = True
        self.page_changed.emit(item_id)
