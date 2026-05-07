import os
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QSizePolicy, QMessageBox, QInputDialog, QApplication,
    QDialog, QProgressBar, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from src.core.i18n import get_translator
from src.services.mysql_service import (
    get_available_mysql_packages, get_installed_instances, install_mysql_instance, uninstall_mysql_instance,
    start_mysql_instance, stop_mysql_instance, restart_mysql_instance, get_instance_status,
    update_mysql_port, update_mysql_root_password, add_mysql_to_path, remove_mysql_from_path,
    is_mysql_in_path, get_mysql_instance_config, get_running_instances, get_instances_in_path
)
from src.core.config import MYSQL_PKG_DIR

MYSQL_OFFICIAL_URL = "https://downloads.mysql.com/archives/community/"
NAVICAT_URL = "https://www.navicat.com/"
VCREDIST_URL = "https://www.microsoft.com/zh-CN/download/details.aspx?id=40784"


class InstallWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, pkg_name: str, port: int, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name
        self._port = port

    def run(self):
        success, message = install_mysql_instance(
            self._pkg_name, self._port,
            progress_callback=lambda step_key, percent: self.progress.emit(step_key, percent)
        )
        self.finished.emit(success, message)


class InstallProgressDialog(QDialog):
    def __init__(self, pkg_name: str, port: int, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name
        self._port = port
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        tr = get_translator()
        self.setWindowTitle(tr.t("mysql.install.dialog.progress_title"))
        self.setFixedSize(450, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        instance_name = self._pkg_name.replace('.zip', '')
        self._title_label = QLabel(tr.t("mysql.install.dialog.installing", instance_name=instance_name))
        self._title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(self._title_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f0f0f0;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #0078D4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress_bar)

        self._step_label = QLabel("")
        self._step_label.setFont(QFont("Microsoft YaHei", 9))
        self._step_label.setStyleSheet("color: #555;")
        layout.addWidget(self._step_label)

    def start_install(self):
        self._worker = InstallWorker(self._pkg_name, self._port, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, step_key: str, percent: int):
        tr = get_translator()
        self._step_label.setText(tr.t(step_key))
        self._progress_bar.setValue(percent)
        QApplication.processEvents()

    def _on_finished(self, success: bool, message: str):
        tr = get_translator()
        self.close()
        if success:
            QMessageBox.information(self.parent(), tr.t("mysql.install.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self.parent(), tr.t("mysql.install.dialog.error_title"), tr.t(message))


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
        self._setup_ui()
        self._load_instances()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)
        tr = get_translator()

        tip_label = QLabel(tr.t("mysql.manage.tip"))
        tip_label.setFont(QFont("Microsoft YaHei", 9))
        tip_label.setStyleSheet("color: #0078D4; font-weight: bold;")
        tip_label.setWordWrap(True)
        self._tip_label = tip_label
        layout.addWidget(tip_label)

        env_note = QLabel(tr.t("mysql.manage.env_note"))
        env_note.setFont(QFont("Microsoft YaHei", 9))
        env_note.setWordWrap(True)
        self._env_note = env_note
        layout.addWidget(env_note)

        navicat_row = QHBoxLayout()
        navicat_label = QLabel(tr.t("mysql.manage.navicat_label"))
        navicat_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        navicat_row.addWidget(navicat_label)
        navicat_link = ClickableLink(NAVICAT_URL, NAVICAT_URL)
        navicat_link.setFont(QFont("Microsoft YaHei", 9))
        navicat_row.addWidget(navicat_link)
        navicat_row.addStretch()
        self._navicat_label = navicat_label
        layout.addLayout(navicat_row)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._load_instances)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            tr.t("mysql.manage.table.name"),
            tr.t("mysql.manage.table.version"),
            tr.t("mysql.manage.table.port"),
            tr.t("mysql.manage.table.status"),
            tr.t("mysql.manage.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _load_instances(self):
        self._table.setRowCount(0)
        instances = get_installed_instances()
        tr = get_translator()

        for instance in instances:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(instance.name))
            self._table.setItem(row, 1, QTableWidgetItem(instance.version))

            port_item = QTableWidgetItem(str(instance.port))
            self._table.setItem(row, 2, port_item)

            status = get_instance_status(instance.name)
            status_text = tr.t(f"mysql.status.{status.lower()}")
            status_item = QTableWidgetItem(status_text)
            if status == "Running":
                status_item.setForeground(QColor("#2E7D32"))
            elif status == "Stopped":
                status_item.setForeground(QColor("#9E9E9E"))
            else:
                status_item.setForeground(QColor("#C62828"))
            self._table.setItem(row, 3, status_item)

            action_widget = QWidget()
            action_outer = QVBoxLayout(action_widget)
            action_outer.setContentsMargins(4, 2, 4, 2)
            action_outer.setSpacing(2)

            row1_layout = QHBoxLayout()
            row1_layout.setSpacing(4)

            start_btn = QPushButton(tr.t("button.start"))
            start_btn.setProperty("instance_name", instance.name)
            start_btn.clicked.connect(self._on_start)
            start_btn.setEnabled(status != "Running")
            row1_layout.addWidget(start_btn)

            stop_btn = QPushButton(tr.t("button.stop"))
            stop_btn.setProperty("instance_name", instance.name)
            stop_btn.clicked.connect(self._on_stop)
            stop_btn.setEnabled(status == "Running")
            row1_layout.addWidget(stop_btn)

            restart_btn = QPushButton(tr.t("button.restart"))
            restart_btn.setProperty("instance_name", instance.name)
            restart_btn.clicked.connect(self._on_restart)
            restart_btn.setEnabled(status == "Running")
            row1_layout.addWidget(restart_btn)

            row2_layout = QHBoxLayout()
            row2_layout.setSpacing(4)

            env_btn = QPushButton(tr.t("mysql.manage.btn.config_env"))
            env_btn.setProperty("instance_name", instance.name)
            env_btn.clicked.connect(self._on_config_env)
            if is_mysql_in_path(instance.name):
                env_btn.setText(tr.t("mysql.manage.btn.remove_env"))
            row2_layout.addWidget(env_btn)

            pwd_btn = QPushButton(tr.t("mysql.manage.btn.change_password"))
            pwd_btn.setProperty("instance_name", instance.name)
            pwd_btn.clicked.connect(self._on_change_password)
            row2_layout.addWidget(pwd_btn)

            port_btn = QPushButton(tr.t("mysql.manage.btn.change_port"))
            port_btn.setProperty("instance_name", instance.name)
            port_btn.clicked.connect(self._on_change_port)
            row2_layout.addWidget(port_btn)

            action_outer.addLayout(row1_layout)
            action_outer.addLayout(row2_layout)

            self._table.setCellWidget(row, 4, action_widget)
            self._table.setRowHeight(row, 58)

    def _on_start(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")

        running = get_running_instances()
        other_running = [n for n in running if n != instance_name]
        if other_running:
            QMessageBox.critical(
                self, tr.t("mysql.manage.dialog.error_title"),
                tr.t("mysql.manage.dialog.running_instances_blocked", instances=", ".join(other_running))
            )
            return

        success, message = start_mysql_instance(instance_name)
        if success:
            QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))
        self._load_instances()

    def _on_stop(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")
        success, message = stop_mysql_instance(instance_name)
        if success:
            QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))
        self._load_instances()

    def _on_restart(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")
        success, message = restart_mysql_instance(instance_name)
        if success:
            QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))
        self._load_instances()

    def _on_config_env(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")
        is_remove = button.text() == tr.t("mysql.manage.btn.remove_env")

        if is_remove:
            reply = QMessageBox.question(
                self, tr.t("mysql.manage.dialog.change_port_title"),
                tr.t("mysql.manage.dialog.confirm_remove_env", instance_name=instance_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            success, message = remove_mysql_from_path(instance_name)
            if success:
                QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"),
                                        tr.t("mysql.manage.dialog.env_removed", instance_name=instance_name))
                self._load_instances()
            else:
                QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))
        else:
            instances_in_path = get_instances_in_path()
            other_in_path = [n for n in instances_in_path if n != instance_name]
            if other_in_path:
                QMessageBox.critical(
                    self, tr.t("mysql.manage.dialog.error_title"),
                    tr.t("mysql.manage.dialog.env_conflict_blocked", instances=", ".join(other_in_path))
                )
                return

            success, message = add_mysql_to_path(instance_name)
            if success:
                QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"),
                                        tr.t("mysql.manage.dialog.env_added", instance_name=instance_name))
                self._load_instances()
            else:
                QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))

    def _on_change_port(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")

        dialog = QDialog(self)
        dialog.setWindowTitle(tr.t("mysql.manage.dialog.change_port_title"))
        dialog.setFixedSize(380, 150)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        dialog.setModal(True)

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(20, 20, 20, 20)
        dlg_layout.setSpacing(12)

        dlg_layout.addWidget(QLabel(tr.t("mysql.manage.dialog.new_port_label")))

        port_input = QLineEdit()
        port_input.setPlaceholderText(tr.t("mysql.manage.dialog.new_port_placeholder"))
        dlg_layout.addWidget(port_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(tr.t("close.btn_cancel"))
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton(tr.t("mysql.manage.btn.confirm"))
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)
        dlg_layout.addLayout(btn_layout)

        def _do_change():
            port_text = port_input.text().strip()
            try:
                new_port = int(port_text)
                if new_port < 1 or new_port > 65535:
                    raise ValueError
            except (ValueError, TypeError):
                QMessageBox.warning(dialog, tr.t("mysql.manage.dialog.error_title"),
                                    tr.t("mysql.manage.dialog.invalid_port"))
                return
            ok_btn.setEnabled(False)
            QApplication.processEvents()
            success, message = update_mysql_port(instance_name, new_port)
            dialog.close()
            if success:
                self._load_instances()
                running = get_running_instances()
                other_running = [n for n in running if n != instance_name]
                if other_running:
                    QMessageBox.warning(
                        self, tr.t("mysql.manage.dialog.warning_title"),
                        tr.t("mysql.manage.dialog.restart_blocked_by_running", instances=", ".join(other_running))
                    )
                else:
                    reply = QMessageBox.question(
                        self, tr.t("mysql.manage.dialog.success_title"),
                        tr.t("mysql.manage.dialog.restart_prompt"),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        restart_success, restart_msg = restart_mysql_instance(instance_name)
                        if restart_success:
                            QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"), tr.t(restart_msg))
                        else:
                            QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(restart_msg))
                        self._load_instances()
            else:
                QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))

        ok_btn.clicked.connect(_do_change)
        dialog.exec()

    def _on_change_password(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")

        instances = get_installed_instances()
        current_instance = next((i for i in instances if i.name == instance_name), None)
        saved_password = current_instance.password if current_instance else ""

        dialog = QDialog(self)
        dialog.setWindowTitle(tr.t("mysql.manage.dialog.change_password_title"))
        dialog.setFixedSize(380, 220)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        dialog.setModal(True)

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(20, 20, 20, 20)
        dlg_layout.setSpacing(10)

        dlg_layout.addWidget(QLabel(tr.t("mysql.manage.dialog.current_password_label")))
        cur_pwd_input = QLineEdit()
        cur_pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        cur_pwd_input.setPlaceholderText(tr.t("mysql.manage.dialog.current_password_placeholder"))
        if saved_password:
            cur_pwd_input.setText(saved_password)
            cur_pwd_input.setEnabled(False)
        dlg_layout.addWidget(cur_pwd_input)

        dlg_layout.addWidget(QLabel(tr.t("mysql.manage.dialog.new_password_label")))
        new_pwd_input = QLineEdit()
        new_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        new_pwd_input.setPlaceholderText(tr.t("mysql.manage.dialog.new_password_placeholder"))
        dlg_layout.addWidget(new_pwd_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(tr.t("close.btn_cancel"))
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton(tr.t("mysql.manage.btn.confirm"))
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)
        dlg_layout.addLayout(btn_layout)

        def _do_change():
            new_pwd = new_pwd_input.text().strip()
            cur_pwd = cur_pwd_input.text().strip()
            if not new_pwd:
                QMessageBox.warning(dialog, tr.t("mysql.manage.dialog.error_title"),
                                    tr.t("mysql.manage.dialog.empty_password"))
                return
            ok_btn.setEnabled(False)
            QApplication.processEvents()
            success, message = update_mysql_root_password(instance_name, new_pwd, current_password=cur_pwd)
            dialog.close()
            if success:
                QMessageBox.information(self, tr.t("mysql.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("mysql.manage.dialog.error_title"), tr.t(message))

        ok_btn.clicked.connect(_do_change)
        dialog.exec()

    def _on_language_changed(self):
        tr = get_translator()
        self._tip_label.setText(tr.t("mysql.manage.tip"))
        self._env_note.setText(tr.t("mysql.manage.env_note"))
        self._navicat_label.setText(tr.t("mysql.manage.navicat_label"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("mysql.manage.table.name"),
            tr.t("mysql.manage.table.version"),
            tr.t("mysql.manage.table.port"),
            tr.t("mysql.manage.table.status"),
            tr.t("mysql.manage.table.actions"),
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
            tr.t("mysql.install.table.name"),
            tr.t("mysql.install.table.status"),
            tr.t("mysql.install.table.path"),
            tr.t("mysql.install.table.actions")
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _setup_info_section(self, layout: QVBoxLayout):
        tr = get_translator()
        self._labels["tip"] = QLabel(tr.t("mysql.install.tip"))
        self._labels["tip"].setFont(QFont("Microsoft YaHei", 9))
        self._labels["tip"].setStyleSheet("color: #E67E22; font-weight: bold;")
        self._labels["tip"].setWordWrap(True)
        layout.addWidget(self._labels["tip"])

        self._labels["custom_note"] = QLabel(tr.t("mysql.install.custom_download_note"))
        self._labels["custom_note"].setFont(QFont("Microsoft YaHei", 9))
        self._labels["custom_note"].setWordWrap(True)
        layout.addWidget(self._labels["custom_note"])

        download_row = QHBoxLayout()
        self._labels["download_label"] = QLabel(tr.t("mysql.install.official_download_label"))
        self._labels["download_label"].setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        download_row.addWidget(self._labels["download_label"])

        link = ClickableLink(MYSQL_OFFICIAL_URL, MYSQL_OFFICIAL_URL)
        link.setFont(QFont("Microsoft YaHei", 9))
        download_row.addWidget(link)
        download_row.addStretch()
        layout.addLayout(download_row)

        vcredist_note = QLabel(tr.t("mysql.install.vcredist_note"))
        vcredist_note.setFont(QFont("Microsoft YaHei", 9))
        vcredist_note.setWordWrap(True)
        self._labels["vcredist_note"] = vcredist_note
        layout.addWidget(vcredist_note)

        vcredist_row = QHBoxLayout()
        self._labels["vcredist_label"] = QLabel(tr.t("mysql.install.vcredist_download_label"))
        self._labels["vcredist_label"].setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        vcredist_row.addWidget(self._labels["vcredist_label"])

        vcredist_link = ClickableLink(VCREDIST_URL, VCREDIST_URL)
        vcredist_link.setFont(QFont("Microsoft YaHei", 9))
        vcredist_row.addWidget(vcredist_link)

        vcredist_local_path = os.path.join(MYSQL_PKG_DIR, "vcredist_x64.exe")
        if os.path.exists(vcredist_local_path):
            self._vcredist_btn = QPushButton(tr.t("mysql.install.btn.install_vcredist"))
            self._vcredist_btn.setFixedHeight(26)
            self._vcredist_btn.setStyleSheet("QPushButton { padding: 2px 8px; font-size: 12px; }")
            self._vcredist_btn.clicked.connect(lambda checked=False, p=vcredist_local_path: os.startfile(p))
            vcredist_row.addWidget(self._vcredist_btn)

        vcredist_row.addStretch()
        layout.addLayout(vcredist_row)

    def _load_packages(self):
        self._table.setRowCount(0)
        available_packages = get_available_mysql_packages()
        installed_instances = {instance.name: instance for instance in get_installed_instances()}

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
                status_item.setText(get_translator().t("mysql.install.status.installed"))
                self._table.setItem(row_position, 2, QTableWidgetItem(installed_instances[instance_name].install_dir))
                uninstall_button = QPushButton(get_translator().t("button.uninstall"))
                uninstall_button.setProperty("package_name", pkg_name)
                uninstall_button.clicked.connect(self._on_uninstall_clicked)
                action_layout.addWidget(uninstall_button)
            else:
                status_item.setText(get_translator().t("mysql.install.status.not_installed"))
                self._table.setItem(row_position, 2, QTableWidgetItem("--"))
                install_button = QPushButton(get_translator().t("button.install"))
                install_button.setProperty("package_name", pkg_name)
                install_button.clicked.connect(self._on_install_clicked)
                action_layout.addWidget(install_button)

            self._table.setItem(row_position, 1, status_item)
            self._table.setCellWidget(row_position, 3, action_widget)

    def _on_install_clicked(self):
        button = self.sender()
        pkg_name = button.property("package_name")
        port = 3306

        button.setEnabled(False)
        button.setText("Installing...")

        dialog = InstallProgressDialog(pkg_name, port, self)
        dialog.start_install()
        dialog.exec()

        self._load_packages()

    def _on_uninstall_clicked(self):
        tr = get_translator()
        button = self.sender()
        pkg_name = button.property("package_name")
        instance_name = pkg_name.replace('.zip', '')

        reply = QMessageBox.question(self, tr.t("mysql.uninstall.dialog.title"),
                                     tr.t("mysql.uninstall.dialog.message", instance_name=instance_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            button.setEnabled(False)
            button.setText("Uninstalling...")
            QApplication.processEvents()

            success, message = uninstall_mysql_instance(instance_name)

            if success:
                QMessageBox.information(self, tr.t("mysql.uninstall.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("mysql.uninstall.dialog.error_title"), tr.t(message))

            self._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["tip"].setText(tr.t("mysql.install.tip"))
        self._labels["custom_note"].setText(tr.t("mysql.install.custom_download_note"))
        self._labels["download_label"].setText(tr.t("mysql.install.official_download_label"))
        self._labels["vcredist_note"].setText(tr.t("mysql.install.vcredist_note"))
        self._labels["vcredist_label"].setText(tr.t("mysql.install.vcredist_download_label"))
        if hasattr(self, "_vcredist_btn"):
            self._vcredist_btn.setText(tr.t("mysql.install.btn.install_vcredist"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("mysql.install.table.name"),
            tr.t("mysql.install.table.status"),
            tr.t("mysql.install.table.path"),
            tr.t("mysql.install.table.actions")
        ])
        self._load_packages()


class MysqlPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tab_widget = QTabWidget()
        self._tabs: dict[str, QWidget] = {}
        self._setup_ui()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tr = get_translator()

        self._tabs["manage"] = ManageTab()
        self._tabs["install"] = InstallTab()

        self._tab_widget.addTab(self._tabs["manage"], tr.t("mysql.nav.manage"))
        self._tab_widget.addTab(self._tabs["install"], tr.t("mysql.nav.install"))
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tab_widget)

    def _on_tab_changed(self, index: int):
        tab = self._tab_widget.widget(index)
        if isinstance(tab, ManageTab):
            tab._load_instances()
        elif isinstance(tab, InstallTab):
            tab._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._tab_widget.setTabText(0, tr.t("mysql.nav.manage"))
        self._tab_widget.setTabText(1, tr.t("mysql.nav.install"))
