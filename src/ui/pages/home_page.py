import webbrowser
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from src.core.i18n import get_translator


GITEE_URL = "https://gitee.com/helloll/wwwoop-env"
GITHUB_URL = "https://github.com/Json870422471/wwwoop-env"


class ClickableLink(QLabel):
    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self._url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("color: #0078D4; text-decoration: underline;")

    def mousePressEvent(self, event):
        webbrowser.open(self._url)
        super().mousePressEvent(event)


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._links: dict[str, ClickableLink] = {}
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

        # 开源地址部分
        opensource_label = QLabel(tr.t("home.opensource_label"))
        opensource_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        opensource_label.setStyleSheet("color: #2C3E50;")
        self._labels["opensource_label"] = opensource_label
        layout.addWidget(opensource_label)

        # Gitee 链接
        gitee_row = QHBoxLayout()
        gitee_text = QLabel("- " + tr.t("home.opensource_gitee") + ": ")
        gitee_text.setFont(QFont("Microsoft YaHei", 10))
        gitee_text.setStyleSheet("color: #555;")
        gitee_row.addWidget(gitee_text)
        gitee_link = ClickableLink(GITEE_URL, GITEE_URL)
        gitee_link.setFont(QFont("Microsoft YaHei", 10))
        gitee_row.addWidget(gitee_link)
        gitee_row.addStretch()
        self._labels["gitee_text"] = gitee_text
        self._links["gitee"] = gitee_link
        layout.addLayout(gitee_row)

        # GitHub 链接
        github_row = QHBoxLayout()
        github_text = QLabel("- " + tr.t("home.opensource_github") + ": ")
        github_text.setFont(QFont("Microsoft YaHei", 10))
        github_text.setStyleSheet("color: #555;")
        github_row.addWidget(github_text)
        github_link = ClickableLink(GITHUB_URL, GITHUB_URL)
        github_link.setFont(QFont("Microsoft YaHei", 10))
        github_row.addWidget(github_link)
        github_row.addStretch()
        self._labels["github_text"] = github_text
        self._links["github"] = github_link
        layout.addLayout(github_row)

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
        self._labels["opensource_label"].setText(tr.t("home.opensource_label"))
        self._labels["gitee_text"].setText("- " + tr.t("home.opensource_gitee") + ": ")
        self._labels["github_text"].setText("- " + tr.t("home.opensource_github") + ": ")
