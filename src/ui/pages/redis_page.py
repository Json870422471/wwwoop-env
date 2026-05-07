import os
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QApplication,
    QDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
from src.core.i18n import get_translator
from src.services.redis_service import (
    get_available_redis_packages, get_installed_instances, install_redis_instance, uninstall_redis_instance,
    start_redis_instance, stop_redis_instance, get_instance_status,
    get_running_instances
)
from src.core.config import REDIS_PKG_DIR, REDIS_INSTALL_DIR

REDIS_GITHUB_URL = "https://github.com/redis-windows/redis-windows"


class ClickableLink(QLabel):
    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self._url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("color: #0078D4; text-decoration: underline;")

    def mousePressEvent(self, event):
        webbrowser.open(self._url)
        super().mousePressEvent(event)


class InstallWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, pkg_name: str):
        super().__init__()
        self._pkg_name = pkg_name

    def run(self):
        success, message = install_redis_instance(
            self._pkg_name, progress_callback=self._on_progress
        )
        self.finished.emit(success, message, self._pkg_name)

    def _on_progress(self, step_key: str, percent: int):
        self.progress.emit(step_key, percent)


class InstallProgressDialog(QDialog):
    def __init__(self, pkg_name: str, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name
        self._success = False
        self._message = ""
        tr = get_translator()

        self.setWindowTitle(tr.t("redis.install.dialog.title"))
        self.setFixedSize(420, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._step_label = QLabel(tr.t("redis.install.dialog.preparing"))
        layout.addWidget(self._step_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

    def start_install(self):
        self._worker = InstallWorker(self._pkg_name)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, step_key: str, percent: int):
        tr = get_translator()
        self._step_label.setText(tr.t(step_key))
        self._progress_bar.setValue(percent)

    def _on_finished(self, success: bool, message: str, pkg_name: str):
        tr = get_translator()
        self._success = success
        self._message = message
        self._progress_bar.setValue(100 if success else self._progress_bar.value())

        if success:
            self._step_label.setText(tr.t("redis.install.dialog.success"))
            self._result_label.setText(tr.t(message))
            self._result_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self._step_label.setText(tr.t("redis.install.dialog.failed"))
            self._result_label.setText(tr.t(message) if message.startswith("redis.") else message)
            self._result_label.setStyleSheet("color: #C62828; font-weight: bold;")

        QApplication.processEvents()
        QTimer.singleShot(1500, self.accept)


class ServiceWorker(QThread):
    finished = pyqtSignal(str, bool, str)

    def __init__(self, action: str, instance_name: str):
        super().__init__()
        self._action = action
        self._instance_name = instance_name

    def run(self):
        if self._action == "start":
            success, message = start_redis_instance(self._instance_name)
        elif self._action == "stop":
            success, message = stop_redis_instance(self._instance_name)
        else:
            success, message = False, "Unknown action"
        self.finished.emit(self._instance_name, success, message)


class ManageTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._service_workers: dict[str, ServiceWorker] = {}
        self._setup_ui()
        self._load_instances()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)
        tr = get_translator()

        tip_label = QLabel(tr.t("redis.manage.tip"))
        tip_label.setFont(QFont("Microsoft YaHei", 9))
        tip_label.setStyleSheet("color: #0078D4; font-weight: bold;")
        tip_label.setWordWrap(True)
        self._tip_label = tip_label
        layout.addWidget(tip_label)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._load_instances)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            tr.t("redis.manage.table.name"),
            tr.t("redis.manage.table.port"),
            tr.t("redis.manage.table.status"),
            tr.t("redis.manage.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _load_instances(self):
        self._table.setRowCount(0)
        instances = get_installed_instances()
        tr = get_translator()

        for row, inst in enumerate(instances):
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(inst.name))
            self._table.setItem(row, 1, QTableWidgetItem(str(inst.port)))

            status = get_instance_status(inst.name)
            if inst.name in self._service_workers:
                worker = self._service_workers[inst.name]
                if worker._action == "start":
                    status = "Starting"
                elif worker._action == "stop":
                    status = "Stopping"

            status_text = tr.t(f"redis.manage.status.{status.lower().replace(' ', '_')}")
            status_item = QTableWidgetItem(status_text)
            if status == "Running":
                status_item.setForeground(QColor("#2E7D32"))
            elif status == "Starting":
                status_item.setForeground(QColor("#FF8C00"))
            elif status == "Stopping":
                status_item.setForeground(QColor("#FF8C00"))
            elif status == "Stopped":
                status_item.setForeground(QColor("#9E9E9E"))
            else:
                status_item.setForeground(QColor("#C62828"))
            self._table.setItem(row, 2, status_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            start_btn = QPushButton(tr.t("redis.manage.btn.start"))
            start_btn.setProperty("instance_name", inst.name)
            start_btn.clicked.connect(self._on_start)
            start_btn.setEnabled(status not in ("Running", "Starting", "Stopping"))
            actions_layout.addWidget(start_btn)

            stop_btn = QPushButton(tr.t("redis.manage.btn.stop"))
            stop_btn.setProperty("instance_name", inst.name)
            stop_btn.clicked.connect(self._on_stop)
            stop_btn.setEnabled(status in ("Running",))
            actions_layout.addWidget(stop_btn)

            actions_layout.addStretch()
            self._table.setCellWidget(row, 3, actions_widget)
            self._table.setRowHeight(row, 40)

    def _on_start(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")

        if instance_name in self._service_workers:
            return

        running = get_running_instances()
        other_running = [n for n in running if n != instance_name]
        if other_running:
            QMessageBox.critical(
                self, tr.t("redis.manage.dialog.error_title"),
                tr.t("redis.manage.dialog.running_instances_blocked", instances=", ".join(other_running))
            )
            return

        self._set_status_text(instance_name, "Starting")
        button.setEnabled(False)

        worker = ServiceWorker("start", instance_name)
        worker.finished.connect(self._on_service_finished)
        self._service_workers[instance_name] = worker
        worker.start()

    def _on_stop(self):
        button = self.sender()
        instance_name = button.property("instance_name")

        if instance_name in self._service_workers:
            return

        self._set_status_text(instance_name, "Stopping")
        button.setEnabled(False)

        worker = ServiceWorker("stop", instance_name)
        worker.finished.connect(self._on_service_finished)
        self._service_workers[instance_name] = worker
        worker.start()

    def _set_status_text(self, instance_name: str, status: str):
        tr = get_translator()
        instances = get_installed_instances()
        for row, inst in enumerate(instances):
            if inst.name == instance_name:
                status_text = tr.t(f"redis.manage.status.{status.lower().replace(' ', '_')}")
                status_item = QTableWidgetItem(status_text)
                if status == "Starting":
                    status_item.setForeground(QColor("#FF8C00"))
                elif status == "Stopping":
                    status_item.setForeground(QColor("#FF8C00"))
                elif status == "Running":
                    status_item.setForeground(QColor("#2E7D32"))
                self._table.setItem(row, 2, status_item)

                actions_widget = self._table.cellWidget(row, 3)
                if actions_widget:
                    for child in actions_widget.findChildren(QPushButton):
                        if child.property("instance_name") == instance_name:
                            if status in ("Starting", "Stopping"):
                                child.setEnabled(False)
                            elif status == "Running":
                                if child.text() == tr.t("redis.manage.btn.stop"):
                                    child.setEnabled(True)
                                else:
                                    child.setEnabled(False)
                            else:
                                if child.text() == tr.t("redis.manage.btn.start"):
                                    child.setEnabled(True)
                                else:
                                    child.setEnabled(False)
                break

    def _on_service_finished(self, instance_name: str, success: bool, message: str):
        tr = get_translator()
        self._service_workers.pop(instance_name, None)

        if success:
            QMessageBox.information(self, tr.t("redis.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("redis.manage.dialog.error_title"), tr.t(message))
        self._load_instances()

    def _on_language_changed(self):
        tr = get_translator()
        self._tip_label.setText(tr.t("redis.manage.tip"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("redis.manage.table.name"),
            tr.t("redis.manage.table.port"),
            tr.t("redis.manage.table.status"),
            tr.t("redis.manage.table.actions"),
        ])
        self._load_instances()


class InstallTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, QLabel] = {}
        self._setup_ui()
        self._load_packages()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tr = get_translator()

        self._setup_info_section(layout)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._load_packages)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            tr.t("redis.install.table.pkg_name"),
            tr.t("redis.install.table.status"),
            tr.t("redis.install.table.path"),
            tr.t("redis.install.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _setup_info_section(self, layout: QVBoxLayout):
        tr = get_translator()

        self._labels["tip"] = QLabel(tr.t("redis.install.tip"))
        self._labels["tip"].setFont(QFont("Microsoft YaHei", 9))
        self._labels["tip"].setStyleSheet("color: #E67E22; font-weight: bold;")
        self._labels["tip"].setWordWrap(True)
        layout.addWidget(self._labels["tip"])

        download_row = QHBoxLayout()
        self._labels["download_label"] = QLabel(tr.t("redis.install.official_download_label"))
        self._labels["download_label"].setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        download_row.addWidget(self._labels["download_label"])

        github_link = ClickableLink(REDIS_GITHUB_URL, REDIS_GITHUB_URL)
        github_link.setFont(QFont("Microsoft YaHei", 9))
        download_row.addWidget(github_link)
        download_row.addStretch()
        layout.addLayout(download_row)

    def _load_packages(self):
        self._table.setRowCount(0)
        available_packages = get_available_redis_packages()
        installed_instances = {instance.name: instance for instance in get_installed_instances()}
        tr = get_translator()

        for pkg_name in available_packages:
            row_position = self._table.rowCount()
            self._table.insertRow(row_position)

            self._table.setItem(row_position, 0, QTableWidgetItem(pkg_name))

            instance_name = pkg_name.replace('.zip', '')
            status_item = QTableWidgetItem()

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 0, 5, 0)

            if instance_name in installed_instances:
                status_item.setText(tr.t("redis.install.status.installed"))
                self._table.setItem(row_position, 2, QTableWidgetItem(installed_instances[instance_name].install_dir))
                uninstall_button = QPushButton(tr.t("button.uninstall"))
                uninstall_button.setProperty("package_name", pkg_name)
                uninstall_button.clicked.connect(self._on_uninstall_clicked)
                action_layout.addWidget(uninstall_button)
            else:
                status_item.setText(tr.t("redis.install.status.not_installed"))
                self._table.setItem(row_position, 2, QTableWidgetItem("--"))
                install_button = QPushButton(tr.t("button.install"))
                install_button.setProperty("package_name", pkg_name)
                install_button.clicked.connect(self._on_install_clicked)
                action_layout.addWidget(install_button)

            self._table.setItem(row_position, 1, status_item)
            self._table.setCellWidget(row_position, 3, action_widget)

    def _on_install_clicked(self):
        button = self.sender()
        pkg_name = button.property("package_name")

        button.setEnabled(False)
        button.setText("Installing...")

        dialog = InstallProgressDialog(pkg_name, self)
        dialog.start_install()
        dialog.exec()

        self._load_packages()

    def _on_uninstall_clicked(self):
        tr = get_translator()
        button = self.sender()
        pkg_name = button.property("package_name")
        instance_name = pkg_name.replace('.zip', '')

        reply = QMessageBox.question(self, tr.t("redis.manage.dialog.confirm_title"),
                                     tr.t("redis.manage.dialog.confirm_uninstall"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            button.setEnabled(False)
            button.setText("Uninstalling...")
            QApplication.processEvents()

            success, message = uninstall_redis_instance(instance_name)

            if success:
                QMessageBox.information(self, tr.t("redis.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("redis.manage.dialog.error_title"), tr.t(message))

            self._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["tip"].setText(tr.t("redis.install.tip"))
        self._labels["download_label"].setText(tr.t("redis.install.official_download_label"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("redis.install.table.pkg_name"),
            tr.t("redis.install.table.status"),
            tr.t("redis.install.table.path"),
            tr.t("redis.install.table.actions"),
        ])
        self._load_packages()


class RedisPage(QWidget):
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

        self._tabs.addTab(self._manage_tab, get_translator().t("redis.tab.manage"))
        self._tabs.addTab(self._install_tab, get_translator().t("redis.tab.install"))

        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

        get_translator().language_changed.connect(self._on_language_changed)

    def _on_tab_changed(self, index: int):
        if index == 0:
            self._manage_tab._load_instances()
        elif index == 1:
            self._install_tab._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._tabs.setTabText(0, tr.t("redis.tab.manage"))
        self._tabs.setTabText(1, tr.t("redis.tab.install"))
