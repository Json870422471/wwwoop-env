import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel,
    QSystemTrayIcon, QMenu, QMessageBox,
)
from PyQt6.QtGui import QFont, QAction, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QEvent

from src.core.config import (
    APP_VERSION,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, NAV_ITEMS,
    ICONS_DIR,
)
from src.core.i18n import get_translator
from src.ui.pages.mysql_page import MysqlPage
from src.ui.pages.php_page import PhpPage
from src.ui.pages.redis_page import RedisPage
from src.ui.pages.java_page import JavaPage
from src.ui.pages.node_page import NodePage
from src.ui.pages.python_page import PythonPage
from src.ui.pages.home_page import HomePage
from src.ui.components.topbar import TopBar
from src.ui.components.footer import Footer
from src.utils.logger import setup_logger

logger = setup_logger("main_window")

NAV_I18N_KEYS = ["nav.home", "nav.mysql", "nav.redis", "nav.java", "nav.php", "nav.python", "nav.node"]


class PlaceholderPage(QWidget):
    def __init__(self, nav_key: str, parent=None):
        super().__init__(parent)
        self._nav_key = nav_key
        layout = QVBoxLayout(self)
        tr = get_translator()
        self._label = QLabel(f"{tr.t(nav_key)} — {tr.t('page.dev')}")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFont(QFont("Microsoft YaHei", 12))
        self._label.setStyleSheet("color: #999999;")
        layout.addWidget(self._label)
        tr.language_changed.connect(self._on_language_changed)

    def _on_language_changed(self):
        tr = get_translator()
        self._label.setText(f"{tr.t(self._nav_key)} — {tr.t('page.dev')}")


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: dict[str, QWidget] = {}
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._tray_show_action: QAction | None = None
        self._tray_quit_action: QAction | None = None
        self._setup_ui()
        self._setup_tray()
        tr = get_translator()
        tr.language_changed.connect(self._on_language_changed)
        self._on_language_changed()
        logger.info(f"{tr.t('app.name')} v{APP_VERSION} 启动完成")

    def _setup_ui(self):
        tr = get_translator()
        self.setWindowTitle(f"{tr.t('app.name')} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._topbar = TopBar()
        self._topbar.page_changed.connect(self._on_page_changed)
        main_layout.addWidget(self._topbar)

        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack, 1)

        self._footer = Footer()
        main_layout.addWidget(self._footer)

        self._register_pages()

    def _register_pages(self):
        for idx, (item_id, _) in enumerate(NAV_ITEMS):
            if item_id == "home":
                page = HomePage()
            elif item_id == "mysql":
                page = MysqlPage()
            elif item_id == "php":
                page = PhpPage()
            elif item_id == "redis":
                page = RedisPage()
            elif item_id == "java":
                page = JavaPage()
            elif item_id == "node":
                page = NodePage()
            elif item_id == "python":
                page = PythonPage()
            else:
                page = PlaceholderPage(NAV_I18N_KEYS[idx])
            self._pages[item_id] = page
            self._stack.addWidget(page)

        first_id = NAV_ITEMS[0][0]
        self._stack.setCurrentWidget(self._pages[first_id])

    def _on_page_changed(self, page_id: str):
        page = self._pages.get(page_id)
        if page:
            self._stack.setCurrentWidget(page)
            logger.info(f"切换到页面: {page_id}")

    def _setup_tray(self):
        self._tray_icon = QSystemTrayIcon(self)

        default_icon = self._create_default_icon()
        self._tray_icon.setIcon(default_icon)
        self.setWindowIcon(default_icon)

        tr = get_translator()
        self._tray_menu = QMenu()
        self._tray_show_action = QAction(tr.t("tray.show"), self)
        self._tray_show_action.triggered.connect(self._show_window)
        self._tray_menu.addAction(self._tray_show_action)

        self._tray_menu.addSeparator()

        self._tray_quit_action = QAction(tr.t("tray.quit"), self)
        self._tray_quit_action.triggered.connect(self._quit_app)
        self._tray_menu.addAction(self._tray_quit_action)

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用")

        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _create_default_icon(self) -> QIcon:
        ico_path = os.path.join(ICONS_DIR, "app.ico")
        if os.path.exists(ico_path):
            return QIcon(ico_path)

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 120, 212))
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "0")
        painter.end()
        return QIcon(pixmap)

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _quit_app(self):
        if self._tray_icon:
            self._tray_icon.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_language_changed(self):
        tr = get_translator()
        self.setWindowTitle(f"{tr.t('app.name')} v{APP_VERSION}")
        if self._tray_show_action:
            self._tray_show_action.setText(tr.t("tray.show"))
        if self._tray_quit_action:
            self._tray_quit_action.setText(tr.t("tray.quit"))

    def closeEvent(self, event):
        tr = get_translator()
        msg = QMessageBox(self)
        msg.setWindowTitle(tr.t("close.title"))
        msg.setText(tr.t("close.text"))
        msg.setInformativeText(
            f"{tr.t('close.minimize_info')}\n{tr.t('close.quit_info')}"
        )
        btn_minimize = msg.addButton(tr.t("close.btn_minimize"), QMessageBox.ButtonRole.AcceptRole)
        btn_quit = msg.addButton(tr.t("close.btn_quit"), QMessageBox.ButtonRole.RejectRole)
        btn_cancel = msg.addButton(tr.t("close.btn_cancel"), QMessageBox.ButtonRole.DestructiveRole)
        msg.setDefaultButton(btn_minimize)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == btn_minimize:
            event.ignore()
            self.hide()
            if self._tray_icon:
                self._tray_icon.showMessage(
                    tr.t("app.name"),
                    tr.t("tray.message"),
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
        elif clicked == btn_quit:
            self._quit_app()
        else:
            event.ignore()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                event.ignore()
                self.hide()
                tr = get_translator()
                if self._tray_icon:
                    self._tray_icon.showMessage(
                        tr.t("app.name"),
                        tr.t("tray.message"),
                        QSystemTrayIcon.MessageIcon.Information,
                        2000,
                    )
                return
        super().changeEvent(event)
