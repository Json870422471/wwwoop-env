import os
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QSizePolicy, QMessageBox, QApplication,
    QDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from src.core.i18n import get_translator
from src.services.php_service import (
    get_available_php_packages, get_installed_instances, install_php_instance, uninstall_php_instance,
    add_php_to_path, remove_php_from_path, is_php_in_path, get_instances_in_path,
    is_composer_installed, install_composer, uninstall_composer,
    add_composer_to_path, remove_composer_from_path, is_composer_in_path
)
from src.core.config import PHP_PKG_DIR, PHP_INSTALL_DIR

PHP_OFFICIAL_URL = "https://www.php.net/"


class InstallWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, pkg_name: str, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name

    def run(self):
        success, message = install_php_instance(
            self._pkg_name,
            progress_callback=lambda step_key, percent: self.progress.emit(step_key, percent)
        )
        self.finished.emit(success, message)


class InstallProgressDialog(QDialog):
    def __init__(self, pkg_name: str, parent=None):
        super().__init__(parent)
        self._pkg_name = pkg_name
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        tr = get_translator()
        self.setWindowTitle(tr.t("php.install.dialog.progress_title"))
        self.setFixedSize(450, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        instance_name = self._pkg_name.replace('.zip', '')
        self._title_label = QLabel(tr.t("php.install.dialog.installing", instance_name=instance_name))
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
        self._worker = InstallWorker(self._pkg_name, self)
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
            QMessageBox.information(self.parent(), tr.t("php.install.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self.parent(), tr.t("php.install.dialog.error_title"), tr.t(message))


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
        self._composer_btns: dict[str, QPushButton] = {}
        self._setup_ui()
        self._load_instances()
        self._load_composer()
        get_translator().language_changed.connect(self._on_language_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)
        tr = get_translator()

        env_note = QLabel(tr.t("php.manage.env_note"))
        env_note.setFont(QFont("Microsoft YaHei", 9))
        env_note.setWordWrap(True)
        self._env_note = env_note
        layout.addWidget(env_note)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._refresh_all)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            tr.t("php.manage.table.name"),
            tr.t("php.manage.table.version"),
            tr.t("php.manage.table.env_status"),
            tr.t("php.manage.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        composer_box = QVBoxLayout()
        composer_box.setSpacing(6)
        self._composer_title = QLabel(tr.t("php.manage.composer_title"))
        self._composer_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        composer_box.addWidget(self._composer_title)

        composer_info = QHBoxLayout()
        self._composer_status_label = QLabel()
        self._composer_status_label.setFont(QFont("Microsoft YaHei", 9))
        composer_info.addWidget(self._composer_status_label)
        composer_info.addStretch()

        self._composer_install_btn = QPushButton(tr.t("php.manage.btn.install_composer"))
        self._composer_install_btn.clicked.connect(self._on_composer_install)
        composer_info.addWidget(self._composer_install_btn)
        self._composer_btns["install"] = self._composer_install_btn

        self._composer_uninstall_btn = QPushButton(tr.t("php.manage.btn.uninstall_composer"))
        self._composer_uninstall_btn.clicked.connect(self._on_composer_uninstall)
        composer_info.addWidget(self._composer_uninstall_btn)
        self._composer_btns["uninstall"] = self._composer_uninstall_btn

        self._composer_env_btn = QPushButton(tr.t("php.manage.btn.config_env"))
        self._composer_env_btn.clicked.connect(self._on_composer_env)
        composer_info.addWidget(self._composer_env_btn)
        self._composer_btns["env"] = self._composer_env_btn

        composer_box.addLayout(composer_info)
        layout.addLayout(composer_box)

    def _refresh_all(self):
        self._load_instances()
        self._load_composer()

    def _load_instances(self):
        self._table.setRowCount(0)
        instances = get_installed_instances()
        tr = get_translator()

        for instance in instances:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(instance.name))
            self._table.setItem(row, 1, QTableWidgetItem(instance.version))

            in_path = is_php_in_path(instance.name)
            env_text = tr.t("php.manage.env_configured") if in_path else tr.t("php.manage.env_not_configured")
            env_item = QTableWidgetItem(env_text)
            if in_path:
                env_item.setForeground(QColor("#2E7D32"))
            else:
                env_item.setForeground(QColor("#9E9E9E"))
            self._table.setItem(row, 2, env_item)

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)

            env_btn = QPushButton(tr.t("php.manage.btn.config_env") if not in_path else tr.t("php.manage.btn.remove_env"))
            env_btn.setProperty("instance_name", instance.name)
            env_btn.clicked.connect(self._on_config_env)
            action_layout.addWidget(env_btn)

            action_layout.addStretch()

            self._table.setCellWidget(row, 3, action_widget)
            self._table.setRowHeight(row, 36)

    def _on_config_env(self):
        tr = get_translator()
        button = self.sender()
        instance_name = button.property("instance_name")
        is_remove = button.text() == tr.t("php.manage.btn.remove_env")

        if is_remove:
            reply = QMessageBox.question(
                self, tr.t("php.manage.dialog.confirm_title"),
                tr.t("php.manage.dialog.confirm_remove_env", instance_name=instance_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            success, message = remove_php_from_path(instance_name)
            if success:
                QMessageBox.information(self, tr.t("php.manage.dialog.success_title"),
                                        tr.t("php.manage.dialog.env_removed", instance_name=instance_name))
                self._load_instances()
            else:
                QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))
        else:
            instances_in_path = get_instances_in_path()
            other_in_path = [n for n in instances_in_path if n != instance_name]
            if other_in_path:
                QMessageBox.critical(
                    self, tr.t("php.manage.dialog.error_title"),
                    tr.t("php.manage.dialog.env_conflict_blocked", instances=", ".join(other_in_path))
                )
                return

            success, message = add_php_to_path(instance_name)
            if success:
                QMessageBox.information(self, tr.t("php.manage.dialog.success_title"),
                                        tr.t("php.manage.dialog.env_added", instance_name=instance_name))
                self._load_instances()
            else:
                QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))

    def _load_composer(self):
        tr = get_translator()
        installed = is_composer_installed()
        in_path = is_composer_in_path()

        if installed:
            env_text = tr.t("php.manage.composer_env_configured") if in_path else tr.t("php.manage.composer_env_not_configured")
            self._composer_status_label.setText(f"Composer — {tr.t('php.install.status.installed')} | {env_text}")
            self._composer_status_label.setStyleSheet("color: #2E7D32;" if in_path else "color: #9E9E9E;")
        else:
            self._composer_status_label.setText(f"Composer — {tr.t('php.install.status.not_installed')}")
            self._composer_status_label.setStyleSheet("color: #9E9E9E;")

        self._composer_install_btn.setVisible(not installed)
        self._composer_uninstall_btn.setVisible(installed)
        self._composer_env_btn.setVisible(installed)
        if installed:
            if in_path:
                self._composer_env_btn.setText(tr.t("php.manage.btn.remove_env"))
            else:
                self._composer_env_btn.setText(tr.t("php.manage.btn.config_env"))

    def _on_composer_install(self):
        tr = get_translator()
        self._composer_install_btn.setEnabled(False)
        QApplication.processEvents()
        success, message = install_composer()
        if success:
            QMessageBox.information(self, tr.t("php.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))
        self._load_composer()

    def _on_composer_uninstall(self):
        tr = get_translator()
        reply = QMessageBox.question(
            self, tr.t("php.manage.dialog.confirm_title"),
            tr.t("php.manage.dialog.confirm_uninstall_composer"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        self._composer_uninstall_btn.setEnabled(False)
        QApplication.processEvents()
        success, message = uninstall_composer()
        if success:
            QMessageBox.information(self, tr.t("php.manage.dialog.success_title"), tr.t(message))
        else:
            QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))
        self._load_composer()

    def _on_composer_env(self):
        tr = get_translator()
        in_path = is_composer_in_path()
        if in_path:
            reply = QMessageBox.question(
                self, tr.t("php.manage.dialog.confirm_title"),
                tr.t("php.manage.dialog.confirm_remove_composer_env"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            success, message = remove_composer_from_path()
            if success:
                QMessageBox.information(self, tr.t("php.manage.dialog.success_title"),
                                        tr.t("php.manage.dialog.composer_env_removed"))
            else:
                QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))
        else:
            success, message = add_composer_to_path()
            if success:
                QMessageBox.information(self, tr.t("php.manage.dialog.success_title"),
                                        tr.t("php.manage.dialog.composer_env_added"))
            else:
                QMessageBox.critical(self, tr.t("php.manage.dialog.error_title"), tr.t(message))
        self._load_composer()

    def _on_language_changed(self):
        tr = get_translator()
        self._env_note.setText(tr.t("php.manage.env_note"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._composer_title.setText(tr.t("php.manage.composer_title"))
        self._composer_install_btn.setText(tr.t("php.manage.btn.install_composer"))
        self._composer_uninstall_btn.setText(tr.t("php.manage.btn.uninstall_composer"))
        self._table.setHorizontalHeaderLabels([
            tr.t("php.manage.table.name"),
            tr.t("php.manage.table.version"),
            tr.t("php.manage.table.env_status"),
            tr.t("php.manage.table.actions"),
        ])
        self._load_instances()
        self._load_composer()


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
        layout.setSpacing(8)
        tr = get_translator()

        tip_label = QLabel(tr.t("php.install.tip"))
        tip_label.setFont(QFont("Microsoft YaHei", 9))
        tip_label.setStyleSheet("color: #0078D4; font-weight: bold;")
        tip_label.setWordWrap(True)
        self._labels["tip"] = tip_label
        layout.addWidget(tip_label)

        custom_note = QLabel(tr.t("php.install.custom_download_note"))
        custom_note.setFont(QFont("Microsoft YaHei", 9))
        custom_note.setWordWrap(True)
        self._labels["custom_note"] = custom_note
        layout.addWidget(custom_note)

        download_row = QHBoxLayout()
        download_label = QLabel(tr.t("php.install.official_download_label"))
        download_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        download_row.addWidget(download_label)
        download_link = ClickableLink(PHP_OFFICIAL_URL, PHP_OFFICIAL_URL)
        download_link.setFont(QFont("Microsoft YaHei", 9))
        download_row.addWidget(download_link)
        download_row.addStretch()
        self._labels["download_label"] = download_label
        layout.addLayout(download_row)

        action_layout = QHBoxLayout()
        self._refresh_button = QPushButton(tr.t("button.refresh"))
        self._refresh_button.clicked.connect(self._load_packages)
        action_layout.addWidget(self._refresh_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            tr.t("php.install.table.name"),
            tr.t("php.install.table.status"),
            tr.t("php.install.table.path"),
            tr.t("php.install.table.actions"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _load_packages(self):
        self._table.setRowCount(0)
        packages = get_available_php_packages()
        tr = get_translator()

        installed_names = set()
        for inst in get_installed_instances():
            installed_names.add(inst.name)

        for pkg_name in packages:
            instance_name = pkg_name.replace('.zip', '')
            is_installed = instance_name in installed_names
            row_position = self._table.rowCount()
            self._table.insertRow(row_position)

            self._table.setItem(row_position, 0, QTableWidgetItem(pkg_name))

            status_text = tr.t("php.install.status.installed") if is_installed else tr.t("php.install.status.not_installed")
            status_item = QTableWidgetItem(status_text)
            if is_installed:
                status_item.setForeground(QColor("#2E7D32"))
            else:
                status_item.setForeground(QColor("#9E9E9E"))
            self._table.setItem(row_position, 1, status_item)

            install_path = os.path.join(PHP_INSTALL_DIR, instance_name)
            self._table.setItem(row_position, 2, QTableWidgetItem(install_path if is_installed else ""))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)

            if is_installed:
                uninstall_btn = QPushButton(tr.t("button.uninstall"))
                uninstall_btn.setProperty("package_name", pkg_name)
                uninstall_btn.clicked.connect(self._on_uninstall_clicked)
                action_layout.addWidget(uninstall_btn)
            else:
                install_btn = QPushButton(tr.t("button.install"))
                install_btn.setProperty("package_name", pkg_name)
                install_btn.clicked.connect(self._on_install_clicked)
                action_layout.addWidget(install_btn)

            action_layout.addStretch()
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

        reply = QMessageBox.question(self, tr.t("php.uninstall.dialog.title"),
                                     tr.t("php.uninstall.dialog.message", instance_name=instance_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            button.setEnabled(False)
            button.setText("Uninstalling...")
            QApplication.processEvents()

            success, message = uninstall_php_instance(instance_name)

            if success:
                QMessageBox.information(self, tr.t("php.uninstall.dialog.success_title"), tr.t(message))
            else:
                QMessageBox.critical(self, tr.t("php.uninstall.dialog.error_title"), tr.t(message))

            self._load_packages()

    def _on_language_changed(self):
        tr = get_translator()
        self._labels["tip"].setText(tr.t("php.install.tip"))
        self._labels["custom_note"].setText(tr.t("php.install.custom_download_note"))
        self._labels["download_label"].setText(tr.t("php.install.official_download_label"))
        self._refresh_button.setText(tr.t("button.refresh"))
        self._table.setHorizontalHeaderLabels([
            tr.t("php.install.table.name"),
            tr.t("php.install.table.status"),
            tr.t("php.install.table.path"),
            tr.t("php.install.table.actions")
        ])
        self._load_packages()


class PhpPage(QWidget):
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

        self._tab_widget.addTab(self._tabs["manage"], tr.t("php.nav.manage"))
        self._tab_widget.addTab(self._tabs["install"], tr.t("php.nav.install"))
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
        self._tab_widget.setTabText(0, tr.t("php.nav.manage"))
        self._tab_widget.setTabText(1, tr.t("php.nav.install"))
