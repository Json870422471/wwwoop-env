import os
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QApplication,
    QDialog, QProgressBar, QLineEdit, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
from src.core.i18n import get_translator
from src.services.java_service import (
    get_available_java_packages, get_installed_instances, install_java_instance, uninstall_java_instance,
    configure_java_env, remove_java_env, is_java_env_configured,
    get_instances_in_path, get_suggested_install_dir,
    is_maven_installed, install_maven, uninstall_maven,
    add_maven_to_path, remove_maven_env, is_maven_in_path, get_maven_install_dir
)
from src.core.config import JAVA_PKG_DIR, JAVA_INSTALL_DIR, MAVEN_INSTALL_DIR

ORACLE_DOWNLOAD_URL = "https://www.oracle.com/java/technologies/downloads/#java21"
OPENJDK_DOWNLOAD_URL = "https://openjdk.org/install/"
MAVEN_DOWNLOAD_URL = "https://maven.apache.org/download.cgi"


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
        success, message = install_java_instance(
            self._pkg_name, progress_callback=self._on_progress
        )
        self.finished.emit(success, message, self._pkg_name)

    def _on_progress(self, step_key: str, percent: int):
        self.progress.emit(step_key, percent)


class InstallProgressDialog(QDialog):
    def __init__(self, pkg_name: str, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name
        tr = get_translator()

        self.setWindowTitle(tr.t("java.install.dialog.title"))
        self.setFixedSize(450, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._step_label = QLabel(tr.t("java.install.dialog.preparing"))
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
        self._progress_bar.setValue(100 if success else self._progress_bar.value())

        if success:
            self._step_label.setText(tr.t("java.install.dialog.success"))
            self._result_label.setText(tr.t(message))
            self._result_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self._step_label.setText(tr.t("java.install.dialog.failed"))
            self._result_label.setText(tr.t(message) if message.startswith("java.") else message)
            self._result_label.setStyleSheet("color: #C62828; font-weight: bold;")

        QApplication.processEvents()
        QTimer.singleShot(1500, self.accept)


class MavenInstallDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        tr = get_translator()
        self._local_repo = ""
        self._use_aliyun = False

        self.setWindowTitle(tr.t("java.maven.install.dialog.title"))
        self.setFixedSize(560, 280)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        repo_label = QLabel(tr.t("java.maven.install.local_repo_label"))
        repo_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        layout.addWidget(repo_label)

        repo_layout = QHBoxLayout()
        self._repo_input = QLineEdit(os.path.join(MAVEN_INSTALL_DIR, ".m2", "repository"))
        self._repo_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CCC;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
            }
        """)
        repo_layout.addWidget(self._repo_input, 1)

        browse_btn = QPushButton(tr.t("java.maven.install.browse"))
        browse_btn.setFixedWidth(60)
        browse_btn.clicked.connect(self._on_browse)
        repo_layout.addWidget(browse_btn)
        layout.addLayout(repo_layout)

        self._aliyun_check = QCheckBox(tr.t("java.maven.install.aliyun_mirror"))
        self._aliyun_check.setChecked(True)
        self._aliyun_check.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self._aliyun_check)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton(tr.t("button.cancel"))
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._install_btn = QPushButton(tr.t("button.install"))
        self._install_btn.setFixedWidth(80)
        self._install_btn.setStyleSheet("QPushButton { background-color: #0078D4; color: white; border-radius: 3px; }")
        self._install_btn.clicked.connect(self._on_install)
        btn_layout.addWidget(self._install_btn)

        layout.addLayout(btn_layout)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, get_translator().t("java.maven.install.select_folder"))
        if folder:
            self._repo_input.setText(folder)

    def _on_install(self):
        self._local_repo = self._repo_input.text().strip()
        self._use_aliyun = self._aliyun_check.isChecked()
        if not self._local_repo:
            QMessageBox.warning(self, get_translator().t("java.manage.dialog.error_title"),
                                get_translator().t("java.service.maven_repo_required"))
            return
        self.accept()

    def get_values(self) -> tuple[str, bool]:
        return self._local_repo, self._use_aliyun


class ManageTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._maven_btns: dict[str, QPushButton] = {}
        self._setup_ui()
        self._load_instances()
        self._load_maven()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)
        tr = get_translator()

        env_note = QLabel(tr.t("java.manage.env_note"))
        env_note.setFont(QFont("Microsoft YaHei", 9))
        env_note.setWordWrap(True)
        self._env_note = env_note
        layout.addWidget(env_note)

        env_note_warning = QLabel(tr.t("java.manage.env_note_warning"))
        env_note_warning.setFont(QFont("Microsoft YaHei", 9))
        env_note_warning.setStyleSheet("color: #E67E22; font-weight: bold;")
        env_note_warning.setWordWrap(True)
        self._env_note_warning = env_note_warning
        layout.addWidget(env_note_warning)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._refresh_all)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            tr.t("java.manage.table.name"),
            tr.t("java.manage.table.version"),
            tr.t("java.manage.table.env_var"),
            tr.t("java.manage.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        maven_box = QVBoxLayout()
        maven_box.setSpacing(6)
        self._maven_title = QLabel(tr.t("java.manage.maven_title"))
        self._maven_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        maven_box.addWidget(self._maven_title)

        maven_info = QHBoxLayout()
        self._maven_status_label = QLabel()
        self._maven_status_label.setFont(QFont("Microsoft YaHei", 9))
        maven_info.addWidget(self._maven_status_label)
        maven_info.addStretch()

        self._maven_install_btn = QPushButton(tr.t("java.manage.btn.install_maven"))
        self._maven_install_btn.clicked.connect(self._on_maven_install)
        maven_info.addWidget(self._maven_install_btn)
        self._maven_btns["install"] = self._maven_install_btn

        self._maven_uninstall_btn = QPushButton(tr.t("java.manage.btn.uninstall_maven"))
        self._maven_uninstall_btn.clicked.connect(self._on_maven_uninstall)
        maven_info.addWidget(self._maven_uninstall_btn)
        self._maven_btns["uninstall"] = self._maven_uninstall_btn

        self._maven_env_btn = QPushButton(tr.t("java.manage.btn.config_env"))
        self._maven_env_btn.clicked.connect(self._on_maven_env)
        maven_info.addWidget(self._maven_env_btn)
        self._maven_btns["env"] = self._maven_env_btn

        maven_box.addLayout(maven_info)

        maven_download_row = QHBoxLayout()
        maven_download_label = QLabel(tr.t("java.manage.maven_download_label"))
        maven_download_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        maven_download_row.addWidget(maven_download_label)
        self._maven_download_label = maven_download_label
        maven_download_link = ClickableLink(MAVEN_DOWNLOAD_URL, MAVEN_DOWNLOAD_URL)
        maven_download_link.setFont(QFont("Microsoft YaHei", 9))
        maven_download_row.addWidget(maven_download_link)
        maven_download_row.addStretch()
        maven_box.addLayout(maven_download_row)

        layout.addLayout(maven_box)

    def _load_instances(self):
        self._table.setRowCount(0)
        instances = get_installed_instances()
        tr = get_translator()

        for row, inst in enumerate(instances):
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(inst.name))
            self._table.setItem(row, 1, QTableWidgetItem(inst.version))

            env_configured = is_java_env_configured(inst.name)
            env_text = tr.t("java.manage.env_configured") if env_configured else tr.t("java.manage.env_not_configured")
            env_item = QTableWidgetItem(env_text)
            env_item.setForeground(QColor("#2E7D32") if env_configured else QColor("#9E9E9E"))
            self._table.setItem(row, 2, env_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            env_btn = QPushButton(tr.t("java.manage.btn.remove_env") if env_configured else tr.t("java.manage.btn.config_env"))
            env_btn.setProperty("instance_name", inst.name)
            env_btn.clicked.connect(self._on_config_env)
            actions_layout.addWidget(env_btn)

            actions_layout.addStretch()
            self._table.setCellWidget(row, 3, actions_widget)
            self._table.setRowHeight(row, 36)

    def _refresh_all(self):
        self._load_instances()
        self._load_maven()

    def _load_maven(self):
        tr = get_translator()
        installed = is_maven_installed()
        if installed:
            self._maven_status_label.setText(tr.t("java.manage.maven_installed"))
            self._maven_status_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
            self._maven_install_btn.setEnabled(False)
            self._maven_install_btn.setText(tr.t("java.manage.btn.install_maven"))
            self._maven_uninstall_btn.setEnabled(True)
            self._maven_uninstall_btn.setText(tr.t("java.manage.btn.uninstall_maven"))
            maven_in_path = is_maven_in_path()
            if maven_in_path:
                self._maven_env_btn.setText(tr.t("java.manage.btn.remove_env"))
            else:
                self._maven_env_btn.setText(tr.t("java.manage.btn.config_env"))
        else:
            self._maven_status_label.setText(tr.t("java.manage.maven_not_installed"))
            self._maven_status_label.setStyleSheet("color: #9E9E9E;")
            self._maven_install_btn.setEnabled(True)
            self._maven_install_btn.setText(tr.t("java.manage.btn.install_maven"))
            self._maven_uninstall_btn.setEnabled(False)
            self._maven_uninstall_btn.setText(tr.t("java.manage.btn.uninstall_maven"))
            self._maven_env_btn.setText(tr.t("java.manage.btn.config_env"))

    def _on_maven_install(self):
        tr = get_translator()
        dialog = MavenInstallDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            local_repo, use_aliyun = dialog.get_values()
            self._maven_install_btn.setEnabled(False)
            self._maven_install_btn.setText("Installing...")
            QApplication.processEvents()
            success, message = install_maven(local_repo=local_repo, use_aliyun_mirror=use_aliyun)
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
            self._load_maven()

    def _on_maven_uninstall(self):
        tr = get_translator()
        reply = QMessageBox.question(
            self, tr.t("java.manage.dialog.confirm_title"),
            tr.t("java.manage.dialog.confirm_uninstall_maven"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._maven_uninstall_btn.setEnabled(False)
            self._maven_uninstall_btn.setText("Uninstalling...")
            QApplication.processEvents()
            success, message = uninstall_maven()
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
            self._load_maven()

    def _on_maven_env(self):
        tr = get_translator()
        if is_maven_in_path():
            reply = QMessageBox.question(
                self, tr.t("java.manage.dialog.confirm_title"),
                tr.t("java.manage.dialog.confirm_remove_env"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            success, message = remove_maven_env()
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
        else:
            success, message = add_maven_to_path()
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
        self._load_maven()

    def _on_config_env(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")
        is_remove = button.text() == tr.t("java.manage.btn.remove_env")

        if is_remove:
            reply = QMessageBox.question(
                self, tr.t("java.manage.dialog.confirm_title"),
                tr.t("java.manage.dialog.confirm_remove_env"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            success, message = remove_java_env(instance_name)
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
        else:
            instances_in_path = get_instances_in_path()
            other_in_path = [n for n in instances_in_path if n != instance_name]
            if other_in_path:
                QMessageBox.critical(
                    self, tr.t("java.manage.dialog.error_title"),
                    tr.t("java.manage.dialog.env_conflict_blocked", instances=", ".join(other_in_path))
                )
                return

            success, message = configure_java_env(instance_name)
            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))
        self._load_instances()

    def _on_language_changed(self):
        tr = get_translator()
        self._env_note.setText(tr.t("java.manage.env_note"))
        self._env_note_warning.setText(tr.t("java.manage.env_note_warning"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._maven_title.setText(tr.t("java.manage.maven_title"))
        self._maven_install_btn.setText(tr.t("java.manage.btn.install_maven"))
        self._maven_uninstall_btn.setText(tr.t("java.manage.btn.uninstall_maven"))
        self._maven_download_label.setText(tr.t("java.manage.maven_download_label"))
        self._table.setHorizontalHeaderLabels([
            tr.t("java.manage.table.name"),
            tr.t("java.manage.table.version"),
            tr.t("java.manage.table.env_var"),
            tr.t("java.manage.table.actions"),
        ])
        self._load_instances()
        self._load_maven()


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
            tr.t("java.install.table.pkg_name"),
            tr.t("java.install.table.status"),
            tr.t("java.install.table.path"),
            tr.t("java.install.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _setup_info_section(self, layout: QVBoxLayout):
        tr = get_translator()

        self._labels["tip"] = QLabel(tr.t("java.install.tip"))
        self._labels["tip"].setFont(QFont("Microsoft YaHei", 9))
        self._labels["tip"].setStyleSheet("color: #E67E22; font-weight: bold;")
        self._labels["tip"].setWordWrap(True)
        layout.addWidget(self._labels["tip"])

        path_tip = QLabel(tr.t("java.install.path_tip"))
        path_tip.setFont(QFont("Microsoft YaHei", 9))
        path_tip.setStyleSheet("color: #0078D4; font-weight: bold;")
        path_tip.setWordWrap(True)
        self._labels["path_tip"] = path_tip
        layout.addWidget(path_tip)

        suggested_row = QHBoxLayout()
        suggested_label = QLabel(tr.t("java.install.suggested_path_label"))
        suggested_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        suggested_row.addWidget(suggested_label)
        self._labels["suggested_label"] = suggested_label

        self._suggested_path_input = QLineEdit(JAVA_INSTALL_DIR)
        self._suggested_path_input.setReadOnly(True)
        self._suggested_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #F5F5F5;
                border: 1px solid #CCC;
                border-radius: 3px;
                padding: 2px 6px;
                color: #333;
            }
        """)
        suggested_row.addWidget(self._suggested_path_input, 1)

        copy_btn = QPushButton(tr.t("java.install.btn.copy_path"))
        copy_btn.setFixedHeight(26)
        copy_btn.setStyleSheet("QPushButton { padding: 2px 8px; font-size: 12px; }")
        copy_btn.clicked.connect(self._on_copy_path)
        self._copy_btn = copy_btn
        suggested_row.addWidget(copy_btn)
        layout.addLayout(suggested_row)

        oracle_row = QHBoxLayout()
        self._labels["oracle_label"] = QLabel(tr.t("java.install.oracle_download_label"))
        self._labels["oracle_label"].setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        oracle_row.addWidget(self._labels["oracle_label"])
        oracle_link = ClickableLink(ORACLE_DOWNLOAD_URL, ORACLE_DOWNLOAD_URL)
        oracle_link.setFont(QFont("Microsoft YaHei", 9))
        oracle_row.addWidget(oracle_link)
        oracle_row.addStretch()
        layout.addLayout(oracle_row)

        openjdk_row = QHBoxLayout()
        self._labels["openjdk_label"] = QLabel(tr.t("java.install.openjdk_download_label"))
        self._labels["openjdk_label"].setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        openjdk_row.addWidget(self._labels["openjdk_label"])
        openjdk_link = ClickableLink(OPENJDK_DOWNLOAD_URL, OPENJDK_DOWNLOAD_URL)
        openjdk_link.setFont(QFont("Microsoft YaHei", 9))
        openjdk_row.addWidget(openjdk_link)
        openjdk_row.addStretch()
        layout.addLayout(openjdk_row)

    def _on_copy_path(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._suggested_path_input.text())
        self._copy_btn.setText("✓")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText(get_translator().t("java.install.btn.copy_path")))

    def _load_packages(self):
        self._table.setRowCount(0)
        available_packages = get_available_java_packages()
        installed_instances = {instance.name: instance for instance in get_installed_instances()}
        tr = get_translator()

        for pkg_name in available_packages:
            row_position = self._table.rowCount()
            self._table.insertRow(row_position)

            self._table.setItem(row_position, 0, QTableWidgetItem(pkg_name))

            instance_name = pkg_name.replace('.exe', '').replace('.zip', '')
            status_item = QTableWidgetItem()

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 0, 5, 0)

            if instance_name in installed_instances:
                inst = installed_instances[instance_name]
                status_item.setText(tr.t("java.install.status.installed"))
                self._table.setItem(row_position, 2, QTableWidgetItem(inst.install_dir or "--"))
                uninstall_button = QPushButton(tr.t("button.uninstall"))
                uninstall_button.setProperty("package_name", pkg_name)
                uninstall_button.clicked.connect(self._on_uninstall_clicked)
                action_layout.addWidget(uninstall_button)
            else:
                status_item.setText(tr.t("java.install.status.not_installed"))
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
        instance_name = pkg_name.replace('.exe', '').replace('.zip', '')

        reply = QMessageBox.question(self, tr.t("java.manage.dialog.confirm_title"),
                                     tr.t("java.manage.dialog.confirm_uninstall"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            button.setEnabled(False)
            button.setText("Uninstalling...")
            QApplication.processEvents()

            success, message = uninstall_java_instance(instance_name)

            if success:
                QMessageBox.information(self, tr.t("java.manage.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("java.manage.dialog.error_title"), tr.t(message))

            self._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["tip"].setText(tr.t("java.install.tip"))
        self._labels["path_tip"].setText(tr.t("java.install.path_tip"))
        self._labels["suggested_label"].setText(tr.t("java.install.suggested_path_label"))
        self._labels["oracle_label"].setText(tr.t("java.install.oracle_download_label"))
        self._labels["openjdk_label"].setText(tr.t("java.install.openjdk_download_label"))
        self._copy_btn.setText(tr.t("java.install.btn.copy_path"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("java.install.table.pkg_name"),
            tr.t("java.install.table.status"),
            tr.t("java.install.table.path"),
            tr.t("java.install.table.actions"),
        ])
        self._load_packages()


class JavaPage(QWidget):
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

        self._tabs.addTab(self._manage_tab, get_translator().t("java.tab.manage"))
        self._tabs.addTab(self._install_tab, get_translator().t("java.tab.install"))

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
        self._tabs.setTabText(0, tr.t("java.tab.manage"))
        self._tabs.setTabText(1, tr.t("java.tab.install"))
