import subprocess
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QPushButton,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from src.core.i18n import get_translator

NODE_OFFICIAL_URL = "https://nodejs.org"
NVM_WINDOWS_URL = "https://github.com/coreybutler/nvm-windows"

COMMAND_STYLE = """
    QLabel {
        font-family: Consolas, 'Courier New', monospace;
        font-size: 13px;
        color: #2C3E50;
        background-color: #F5F6FA;
        border: 1px solid #E0E0E0;
        border-radius: 3px;
        padding: 4px 8px;
    }
"""

COPY_BTN_STYLE = """
    QPushButton {
        background-color: transparent;
        border: 1px solid #CCC;
        border-radius: 3px;
        padding: 2px 8px;
        font-size: 11px;
        color: #666;
    }
    QPushButton:hover {
        background-color: #E8E8E8;
        color: #333;
    }
"""


class ClickableLink(QLabel):
    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self._url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("color: #0078D4; text-decoration: underline;")

    def mousePressEvent(self, event):
        webbrowser.open(self._url)
        super().mousePressEvent(event)


class ManageTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tr = get_translator()

        title = QLabel(tr.t("node.manage.title"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self._labels["title"] = title
        layout.addWidget(title)

        desc = QLabel(tr.t("node.manage.desc"))
        desc.setFont(QFont("Microsoft YaHei", 9))
        desc.setWordWrap(True)
        self._labels["desc"] = desc
        layout.addWidget(desc)

        layout.addSpacing(8)

        section_title = QLabel(tr.t("node.manage.cmd_section"))
        section_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section_title"] = section_title
        layout.addWidget(section_title)

        commands = [
            ("node -v", "node.manage.cmd.node_v"),
            ("npm -v", "node.manage.cmd.npm_v"),
            ("nvm -v", "node.manage.cmd.nvm_v"),
            ("nvm list", "node.manage.cmd.nvm_list"),
            ("nvm list available", "node.manage.cmd.nvm_list_available"),
            ("nvm install <version>", "node.manage.cmd.nvm_install"),
            ("nvm uninstall <version>", "node.manage.cmd.nvm_uninstall"),
            ("nvm use <version>", "node.manage.cmd.nvm_use"),
        ]

        self._cmd_labels: list[tuple[QLabel, QLabel, str]] = []
        for cmd, desc_key in commands:
            row = QHBoxLayout()
            row.setSpacing(8)
            cmd_label = QLabel(cmd)
            cmd_label.setStyleSheet(COMMAND_STYLE)
            cmd_label.setFixedWidth(220)
            row.addWidget(cmd_label)

            copy_btn = QPushButton(tr.t("button.copy"))
            copy_btn.setFixedWidth(50)
            copy_btn.setFixedHeight(24)
            copy_btn.setStyleSheet(COPY_BTN_STYLE)
            copy_btn.clicked.connect(lambda checked, c=cmd, b=copy_btn: self._on_copy(c, b))
            row.addWidget(copy_btn)

            desc_label = QLabel(tr.t(desc_key))
            desc_label.setFont(QFont("Microsoft YaHei", 9))
            desc_label.setWordWrap(True)
            row.addWidget(desc_label, 1)
            layout.addLayout(row)
            self._cmd_labels.append((cmd_label, desc_label, desc_key, copy_btn))

        layout.addSpacing(12)

        btn_row = QHBoxLayout()
        self._open_cmd_btn = QPushButton(tr.t("node.manage.open_cmd"))
        self._open_cmd_btn.setFixedWidth(140)
        self._open_cmd_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
        self._open_cmd_btn.clicked.connect(self._on_open_cmd)
        btn_row.addWidget(self._open_cmd_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

    def _on_copy(self, text: str, btn: QPushButton):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        tr = get_translator()
        btn.setText(tr.t("button.copied"))
        btn.setStyleSheet(COPY_BTN_STYLE + "QPushButton { color: #2E7D32; }")
        QTimer.singleShot(1500, lambda: self._restore_copy_btn(btn))

    def _restore_copy_btn(self, btn: QPushButton):
        tr = get_translator()
        btn.setText(tr.t("button.copy"))
        btn.setStyleSheet(COPY_BTN_STYLE)

    def _on_open_cmd(self):
        subprocess.Popen("cmd.exe", creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["title"].setText(tr.t("node.manage.title"))
        self._labels["desc"].setText(tr.t("node.manage.desc"))
        self._labels["section_title"].setText(tr.t("node.manage.cmd_section"))
        self._open_cmd_btn.setText(tr.t("node.manage.open_cmd"))
        for cmd_label, desc_label, desc_key, copy_btn in self._cmd_labels:
            desc_label.setText(tr.t(desc_key))
            copy_btn.setText(tr.t("button.copy"))


class InstallTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tr = get_translator()

        title = QLabel(tr.t("node.install.title"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self._labels["title"] = title
        layout.addWidget(title)

        layout.addSpacing(8)

        section1_title = QLabel(tr.t("node.install.section1_title"))
        section1_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section1_title"] = section1_title
        layout.addWidget(section1_title)

        section1_desc = QLabel(tr.t("node.install.section1_desc"))
        section1_desc.setFont(QFont("Microsoft YaHei", 9))
        section1_desc.setWordWrap(True)
        self._labels["section1_desc"] = section1_desc
        layout.addWidget(section1_desc)

        node_url_row = QHBoxLayout()
        node_url_label = QLabel(tr.t("node.install.official_label"))
        node_url_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self._labels["official_label"] = node_url_label
        node_url_row.addWidget(node_url_label)
        node_url_link = ClickableLink(NODE_OFFICIAL_URL, NODE_OFFICIAL_URL)
        node_url_link.setFont(QFont("Microsoft YaHei", 9))
        node_url_row.addWidget(node_url_link)
        node_url_row.addStretch()
        layout.addLayout(node_url_row)

        layout.addSpacing(12)

        section2_title = QLabel(tr.t("node.install.section2_title"))
        section2_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section2_title"] = section2_title
        layout.addWidget(section2_title)

        section2_desc = QLabel(tr.t("node.install.section2_desc"))
        section2_desc.setFont(QFont("Microsoft YaHei", 9))
        section2_desc.setWordWrap(True)
        self._labels["section2_desc"] = section2_desc
        layout.addWidget(section2_desc)

        nvm_url_row = QHBoxLayout()
        nvm_url_label = QLabel(tr.t("node.install.nvm_label"))
        nvm_url_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self._labels["nvm_label"] = nvm_url_label
        nvm_url_row.addWidget(nvm_url_label)
        nvm_url_link = ClickableLink(NVM_WINDOWS_URL, NVM_WINDOWS_URL)
        nvm_url_link.setFont(QFont("Microsoft YaHei", 9))
        nvm_url_row.addWidget(nvm_url_link)
        nvm_url_row.addStretch()
        layout.addLayout(nvm_url_row)

        layout.addSpacing(12)

        disclaimer = QLabel(tr.t("node.install.disclaimer"))
        disclaimer.setFont(QFont("Microsoft YaHei", 9))
        disclaimer.setStyleSheet("color: #E67E22; font-weight: bold;")
        disclaimer.setWordWrap(True)
        self._labels["disclaimer"] = disclaimer
        layout.addWidget(disclaimer)

        layout.addStretch()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["title"].setText(tr.t("node.install.title"))
        self._labels["section1_title"].setText(tr.t("node.install.section1_title"))
        self._labels["section1_desc"].setText(tr.t("node.install.section1_desc"))
        self._labels["official_label"].setText(tr.t("node.install.official_label"))
        self._labels["section2_title"].setText(tr.t("node.install.section2_title"))
        self._labels["section2_desc"].setText(tr.t("node.install.section2_desc"))
        self._labels["nvm_label"].setText(tr.t("node.install.nvm_label"))
        self._labels["disclaimer"].setText(tr.t("node.install.disclaimer"))


class NodePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()

        self._manage_tab = ManageTab()
        self._install_tab = InstallTab()

        self._tabs.addTab(self._manage_tab, get_translator().t("node.tab.manage"))
        self._tabs.addTab(self._install_tab, get_translator().t("node.tab.install"))

        layout.addWidget(self._tabs)

        get_translator().language_changed.connect(self._on_language_changed)

    def _on_language_changed(self):
        tr = get_translator()
        self._tabs.setTabText(0, tr.t("node.tab.manage"))
        self._tabs.setTabText(1, tr.t("node.tab.install"))
