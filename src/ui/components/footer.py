import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor

from src.core.config import FOOTER_HEIGHT, WEBSITE_URL
from src.core.i18n import get_translator


class ClickableLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):
        webbrowser.open(WEBSITE_URL)
        super().mousePressEvent(event)


class Footer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(FOOTER_HEIGHT)
        self._desc_label: QLabel | None = None
        self._link_label: ClickableLabel | None = None
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        tr = get_translator()
        self._desc_label = QLabel(tr.t("app.description"))
        self._desc_label.setFont(QFont("Microsoft YaHei", 9))
        self._desc_label.setStyleSheet("color: #E74C3C;")
        self._desc_label.setWordWrap(True)
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._desc_label, 3)

        layout.addSpacing(12)

        self._link_label = ClickableLabel(tr.t("app.website_label"))
        self._link_label.setFont(QFont("Microsoft YaHei", 9))
        self._link_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
        self._link_label.setWordWrap(True)
        self._link_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._link_label, 2)

    def _on_language_changed(self):
        tr = get_translator()
        self._desc_label.setText(tr.t("app.description"))
        self._link_label.setText(tr.t("app.website_label"))
