import sys
import ctypes
import ctypes.wintypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from src.core.i18n import get_translator
from src.ui.main_window import MainWindow
from src.utils.logger import setup_logger

logger = setup_logger("app")

MUTEX_NAME = "Global\\WWWOOP_DEV_ENV_SINGLE_INSTANCE"


def check_single_instance() -> ctypes.wintypes.HANDLE | None:
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if last_error == 183:
            return None
        return mutex
    except Exception as e:
        logger.error(f"Single instance check failed: {e}")
        return True


def create_app() -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName(get_translator().t("app.name"))

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    app.setStyleSheet(
        """
        QToolTip {
            background-color: #2C3E50;
            color: #ECF0F1;
            border: 1px solid #34495E;
            border-radius: 4px;
            padding: 4px 8px;
        }
        """
    )

    return app


def run():
    logger.info(f"正在启动 {get_translator().t('app.name')}...")

    mutex = check_single_instance()
    if mutex is None:
        logger.warning("Application already running")
        app = QApplication(sys.argv)
        tr = get_translator()
        QMessageBox.warning(None, tr.t("app.name"), tr.t("app.already_running"))
        sys.exit(1)

    app = create_app()

    window = MainWindow()
    window.show()

    exit_code = app.exec()

    try:
        if mutex and mutex is not True:
            ctypes.windll.kernel32.ReleaseMutex(mutex)
            ctypes.windll.kernel32.CloseHandle(mutex)
    except Exception:
        pass

    sys.exit(exit_code)
