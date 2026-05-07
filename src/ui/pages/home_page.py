from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from src.core.i18n import get_translator


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tr = get_translator()

        app_name = QLabel(tr.t("home.app_name"))
        app_name.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        app_name.setStyleSheet("color: #2C3E50;")
        self._labels["app_name"] = app_name
        layout.addWidget(app_name)

        app_desc = QLabel(tr.t("home.app_desc"))
        app_desc.setFont(QFont("Microsoft YaHei", 10))
        app_desc.setWordWrap(True)
        app_desc.setStyleSheet("color: #555;")
        self._labels["app_desc"] = app_desc
        layout.addWidget(app_desc)

        layout.addSpacing(12)

        env_title = QLabel(tr.t("home.env_title"))
        env_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        env_title.setStyleSheet("color: #2C3E50;")
        self._labels["env_title"] = env_title
        layout.addWidget(env_title)

        env_desc = QLabel(tr.t("home.env_desc"))
        env_desc.setFont(QFont("Microsoft YaHei", 10))
        env_desc.setWordWrap(True)
        env_desc.setStyleSheet("color: #555;")
        self._labels["env_desc"] = env_desc
        layout.addWidget(env_desc)

        env_tip = QLabel(tr.t("home.env_tip"))
        env_tip.setFont(QFont("Microsoft YaHei", 10))
        env_tip.setStyleSheet("color: #E67E22; font-weight: bold;")
        env_tip.setWordWrap(True)
        self._labels["env_tip"] = env_tip
        layout.addWidget(env_tip)

        layout.addSpacing(16)

        disclaimer_title = QLabel(tr.t("home.disclaimer_title"))
        disclaimer_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        disclaimer_title.setStyleSheet("color: #2C3E50;")
        self._labels["disclaimer_title"] = disclaimer_title
        layout.addWidget(disclaimer_title)

        disclaimer_desc = QLabel(tr.t("home.disclaimer_desc"))
        disclaimer_desc.setFont(QFont("Microsoft YaHei", 10))
        disclaimer_desc.setWordWrap(True)
        disclaimer_desc.setStyleSheet("color: #555;")
        self._labels["disclaimer_desc"] = disclaimer_desc
        layout.addWidget(disclaimer_desc)

        layout.addStretch()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["app_name"].setText(tr.t("home.app_name"))
        self._labels["app_desc"].setText(tr.t("home.app_desc"))
        self._labels["env_title"].setText(tr.t("home.env_title"))
        self._labels["env_desc"].setText(tr.t("home.env_desc"))
        self._labels["env_tip"].setText(tr.t("home.env_tip"))
        self._labels["disclaimer_title"].setText(tr.t("home.disclaimer_title"))
        self._labels["disclaimer_desc"].setText(tr.t("home.disclaimer_desc"))
