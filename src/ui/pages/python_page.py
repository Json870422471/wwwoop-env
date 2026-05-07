import os
import subprocess
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QPushButton,
    QApplication, QLineEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from src.core.i18n import get_translator

MINICONDA_OFFICIAL_URL = "https://docs.conda.io/projects/miniconda/en/latest/"
MINICONDA_TSINGHUA_URL = "https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/"

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

OPEN_CMD_BTN_STYLE = """
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

        title = QLabel(tr.t("python.manage.title"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self._labels["title"] = title
        layout.addWidget(title)

        desc = QLabel(tr.t("python.manage.desc"))
        desc.setFont(QFont("Microsoft YaHei", 9))
        desc.setWordWrap(True)
        self._labels["desc"] = desc
        layout.addWidget(desc)

        layout.addSpacing(8)

        section_title = QLabel(tr.t("python.manage.cmd_section"))
        section_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section_title"] = section_title
        layout.addWidget(section_title)

        commands = [
            ("conda -V", "python.manage.cmd.conda_v"),
            ("conda env list", "python.manage.cmd.conda_env_list"),
            ("conda create -n <name> python=<version>", "python.manage.cmd.conda_create"),
            ("conda activate <name>", "python.manage.cmd.conda_activate"),
            ("conda deactivate", "python.manage.cmd.conda_deactivate"),
            ("conda remove -n <name> --all", "python.manage.cmd.conda_remove"),
            ("conda install <package>", "python.manage.cmd.conda_install"),
            ("pip install <package>", "python.manage.cmd.pip_install"),
            ("python -V", "python.manage.cmd.python_v"),
        ]

        self._cmd_labels: list[tuple[QLabel, QLabel, str, QPushButton]] = []
        for cmd, desc_key in commands:
            row = QHBoxLayout()
            row.setSpacing(8)
            cmd_label = QLabel(cmd)
            cmd_label.setStyleSheet(COMMAND_STYLE)
            cmd_label.setFixedWidth(300)
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

        dir_row = QHBoxLayout()
        dir_label = QLabel(tr.t("python.manage.work_dir"))
        dir_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        dir_row.addWidget(dir_label)
        self._labels["work_dir"] = dir_label

        self._dir_input = QLineEdit()
        self._dir_input.setPlaceholderText(tr.t("python.manage.work_dir_placeholder"))
        self._dir_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CCC;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
            }
        """)
        dir_row.addWidget(self._dir_input, 1)

        browse_btn = QPushButton(tr.t("python.manage.browse"))
        browse_btn.setFixedWidth(60)
        browse_btn.setStyleSheet(COPY_BTN_STYLE)
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(browse_btn)
        self._browse_btn = browse_btn
        layout.addLayout(dir_row)

        work_dir_desc = QLabel(tr.t("python.manage.work_dir_desc"))
        work_dir_desc.setFont(QFont("Microsoft YaHei", 9))
        work_dir_desc.setStyleSheet("color: #666;")
        work_dir_desc.setWordWrap(True)
        self._labels["work_dir_desc"] = work_dir_desc
        layout.addWidget(work_dir_desc)

        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        self._open_cmd_btn = QPushButton(tr.t("python.manage.open_cmd"))
        self._open_cmd_btn.setFixedWidth(160)
        self._open_cmd_btn.setStyleSheet(OPEN_CMD_BTN_STYLE)
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

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, get_translator().t("python.manage.select_folder"))
        if folder:
            self._dir_input.setText(folder)

    def _on_open_cmd(self):
        work_dir = self._dir_input.text().strip()
        if work_dir and os.path.isdir(work_dir):
            subprocess.Popen("cmd.exe", cwd=work_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen("cmd.exe", creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["title"].setText(tr.t("python.manage.title"))
        self._labels["desc"].setText(tr.t("python.manage.desc"))
        self._labels["section_title"].setText(tr.t("python.manage.cmd_section"))
        self._labels["work_dir"].setText(tr.t("python.manage.work_dir"))
        self._labels["work_dir_desc"].setText(tr.t("python.manage.work_dir_desc"))
        self._dir_input.setPlaceholderText(tr.t("python.manage.work_dir_placeholder"))
        self._browse_btn.setText(tr.t("python.manage.browse"))
        self._open_cmd_btn.setText(tr.t("python.manage.open_cmd"))
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

        title = QLabel(tr.t("python.install.title"))
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self._labels["title"] = title
        layout.addWidget(title)

        layout.addSpacing(8)

        section1_title = QLabel(tr.t("python.install.section1_title"))
        section1_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section1_title"] = section1_title
        layout.addWidget(section1_title)

        section1_desc = QLabel(tr.t("python.install.section1_desc"))
        section1_desc.setFont(QFont("Microsoft YaHei", 9))
        section1_desc.setWordWrap(True)
        self._labels["section1_desc"] = section1_desc
        layout.addWidget(section1_desc)

        official_row = QHBoxLayout()
        official_label = QLabel(tr.t("python.install.official_label"))
        official_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self._labels["official_label"] = official_label
        official_row.addWidget(official_label)
        official_link = ClickableLink(MINICONDA_OFFICIAL_URL, MINICONDA_OFFICIAL_URL)
        official_link.setFont(QFont("Microsoft YaHei", 9))
        official_row.addWidget(official_link)
        official_row.addStretch()
        layout.addLayout(official_row)

        tsinghua_row = QHBoxLayout()
        tsinghua_label = QLabel(tr.t("python.install.tsinghua_label"))
        tsinghua_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        tsinghua_label.setStyleSheet("color: #E67E22;")
        self._labels["tsinghua_label"] = tsinghua_label
        tsinghua_row.addWidget(tsinghua_label)
        tsinghua_link = ClickableLink(MINICONDA_TSINGHUA_URL, MINICONDA_TSINGHUA_URL)
        tsinghua_link.setFont(QFont("Microsoft YaHei", 9))
        tsinghua_row.addWidget(tsinghua_link)
        tsinghua_row.addStretch()
        layout.addLayout(tsinghua_row)

        layout.addSpacing(12)

        section2_title = QLabel(tr.t("python.install.section2_title"))
        section2_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self._labels["section2_title"] = section2_title
        layout.addWidget(section2_title)

        section2_desc = QLabel(tr.t("python.install.section2_desc"))
        section2_desc.setFont(QFont("Microsoft YaHei", 9))
        section2_desc.setWordWrap(True)
        self._labels["section2_desc"] = section2_desc
        layout.addWidget(section2_desc)

        layout.addStretch()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["title"].setText(tr.t("python.install.title"))
        self._labels["section1_title"].setText(tr.t("python.install.section1_title"))
        self._labels["section1_desc"].setText(tr.t("python.install.section1_desc"))
        self._labels["official_label"].setText(tr.t("python.install.official_label"))
        self._labels["tsinghua_label"].setText(tr.t("python.install.tsinghua_label"))
        self._labels["section2_title"].setText(tr.t("python.install.section2_title"))
        self._labels["section2_desc"].setText(tr.t("python.install.section2_desc"))


class PythonPage(QWidget):
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

        self._tabs.addTab(self._manage_tab, get_translator().t("python.tab.manage"))
        self._tabs.addTab(self._install_tab, get_translator().t("python.tab.install"))

        layout.addWidget(self._tabs)

        get_translator().language_changed.connect(self._on_language_changed)

    def _on_language_changed(self):
        tr = get_translator()
        self._tabs.setTabText(0, tr.t("python.tab.manage"))
        self._tabs.setTabText(1, tr.t("python.tab.install"))
