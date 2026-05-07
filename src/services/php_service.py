import os
import subprocess
import zipfile
import shutil
import json
import winreg
from src.core.config import PHP_PKG_DIR, PHP_INSTALL_DIR, COMPOSER_PKG_PATH, COMPOSER_INSTALL_DIR
from src.utils.logger import setup_logger

logger = setup_logger("php_service")


class PHPInstance:
    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.install_dir = os.path.join(PHP_INSTALL_DIR, self.name)
        self.meta_file = os.path.join(self.install_dir, "instance.json")

    def save_metadata(self):
        meta = {"name": self.name, "version": self.version}
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f)

    @classmethod
    def load_from_metadata(cls, path: str):
        try:
            with open(os.path.join(path, "instance.json"), 'r', encoding='utf-8') as f:
                meta = json.load(f)
            return cls(name=meta['name'], version=meta['version'])
        except (FileNotFoundError, json.JSONDecodeError):
            return None


def _run_command(command: list[str], cwd: str | None = None) -> tuple[bool, str]:
    try:
        logger.info(f"Running command: {' '.join(command)}")
        process = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=True,
            encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info(process.stdout)
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command)}")
        logger.error(f"Stderr: {e.stderr}")
        logger.error(f"Stdout: {e.stdout}")
        return False, e.stderr or e.stdout or str(e)
    except FileNotFoundError as e:
        logger.error(f"Command not found: {e}")
        return False, str(e)


def get_available_php_packages() -> list[str]:
    if not os.path.exists(PHP_PKG_DIR):
        os.makedirs(PHP_PKG_DIR)
        return []
    packages = [
        f
        for f in os.listdir(PHP_PKG_DIR)
        if f.endswith(".zip") and os.path.isfile(os.path.join(PHP_PKG_DIR, f))
    ]
    return packages


def install_php_instance(pkg_name: str, progress_callback=None) -> tuple[bool, str]:
    def _report(step_key: str, percent: int):
        if progress_callback:
            progress_callback(step_key, percent)

    instance_name = pkg_name.replace('.zip', '')
    logger.info(f"Starting installation for PHP instance '{instance_name}' from '{pkg_name}'")

    zip_path = os.path.join(PHP_PKG_DIR, pkg_name)
    instance = PHPInstance(name=instance_name, version=_extract_version(instance_name))

    if not os.path.exists(zip_path):
        return False, "php.service.pkg_not_found"
    if os.path.exists(instance.install_dir):
        return False, "php.service.dir_already_exists"

    try:
        logger.info(f"Extracting '{zip_path}' to '{instance.install_dir}'")
        _report("php.install.step.extract", 30)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            extract_temp_dir = instance.install_dir + "_temp"
            zip_ref.extractall(extract_temp_dir)

            _report("php.install.step.move", 60)
            extracted_items = os.listdir(extract_temp_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_temp_dir, extracted_items[0])):
                extracted_folder = os.path.join(extract_temp_dir, extracted_items[0])
                os.makedirs(instance.install_dir, exist_ok=True)
                for item in os.listdir(extracted_folder):
                    shutil.move(os.path.join(extracted_folder, item), instance.install_dir)
                shutil.rmtree(extract_temp_dir)
            else:
                os.makedirs(instance.install_dir, exist_ok=True)
                for item in extracted_items:
                    shutil.move(os.path.join(extract_temp_dir, item), instance.install_dir)
                shutil.rmtree(extract_temp_dir)

        php_ini_dev = os.path.join(instance.install_dir, "php.ini-development")
        php_ini_prod = os.path.join(instance.install_dir, "php.ini-production")
        php_ini = os.path.join(instance.install_dir, "php.ini")
        if not os.path.exists(php_ini):
            if os.path.exists(php_ini_dev):
                shutil.copy2(php_ini_dev, php_ini)
                logger.info(f"Copied php.ini-development to php.ini for '{instance.name}'")
            elif os.path.exists(php_ini_prod):
                shutil.copy2(php_ini_prod, php_ini)
                logger.info(f"Copied php.ini-production to php.ini for '{instance.name}'")

        _report("php.install.step.save_metadata", 100)
        instance.save_metadata()

        logger.info(f"Installation successful for PHP instance '{instance.name}'")
        return True, "php.service.install_success"

    except Exception as e:
        logger.error(f"Installation failed for PHP instance '{instance.name}': {e}")
        if os.path.exists(instance.install_dir):
            shutil.rmtree(instance.install_dir)
        return False, str(e)


def uninstall_php_instance(instance_name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to uninstall PHP instance '{instance_name}'")
    instance_dir = os.path.join(PHP_INSTALL_DIR, instance_name)
    if not os.path.exists(instance_dir):
        return False, "php.service.dir_not_found"

    _remove_path_env(instance_dir)

    try:
        shutil.rmtree(instance_dir)
        logger.info(f"Successfully removed PHP instance directory '{instance_dir}'")
        return True, "php.service.uninstall_success"
    except OSError as e:
        logger.error(f"Failed to remove PHP instance directory '{instance_dir}': {e}")
        return False, "php.service.remove_dir_failed"


def _extract_version(instance_name: str) -> str:
    parts = instance_name.split('-')
    for part in parts:
        if part and part[0].isdigit():
            return part
    return instance_name


def get_installed_instances() -> list[PHPInstance]:
    if not os.path.exists(PHP_INSTALL_DIR):
        os.makedirs(PHP_INSTALL_DIR)
        return []
    instances = []
    for dir_name in os.listdir(PHP_INSTALL_DIR):
        path = os.path.join(PHP_INSTALL_DIR, dir_name)
        if os.path.isdir(path):
            instance = PHPInstance.load_from_metadata(path)
            if instance:
                instances.append(instance)
    return instances


def get_instances_in_path() -> list[str]:
    in_path = []
    for inst in get_installed_instances():
        if is_php_in_path(inst.name):
            in_path.append(inst.name)
    return in_path


def get_php_version(instance_name: str) -> str | None:
    instance_dir = os.path.join(PHP_INSTALL_DIR, instance_name)
    php_exe = os.path.join(instance_dir, "php.exe")
    if not os.path.exists(php_exe):
        return None
    success, output = _run_command([php_exe, "-v"])
    if success and output:
        first_line = output.strip().split('\n')[0]
        return first_line
    return None


_HKLM_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
_HKCU_ENV = r"Environment"


def _read_path_hklm() -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None


def _read_path_hkcu() -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None


def _write_path_hklm(new_path: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        from ctypes import windll
        windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKLM PATH: {e}")
        return False


def _write_path_hkcu(new_path: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        from ctypes import windll
        windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKCU PATH: {e}")
        return False


def _find_dir_in_path(dir_path: str) -> str | None:
    dir_norm = dir_path.rstrip("\\").lower()
    for scope, reader in [("hklm", _read_path_hklm), ("hkcu", _read_path_hkcu)]:
        current = reader()
        if current is None:
            continue
        for p in current.split(";"):
            if p.strip().rstrip("\\").lower() == dir_norm:
                return scope
    return None


def _add_path_env(dir_path: str) -> tuple[bool, str]:
    dir_path = dir_path.rstrip("\\")
    existing = _find_dir_in_path(dir_path)
    if existing:
        return True, "php.service.already_in_path"

    hklm_ok = False
    hkcu_ok = False

    hklm_path = _read_path_hklm()
    if hklm_path is not None:
        paths = [p.strip() for p in hklm_path.split(";") if p.strip()]
        paths.append(dir_path)
        hklm_ok = _write_path_hklm(";".join(paths))
        if hklm_ok:
            logger.info(f"Added '{dir_path}' to system PATH (HKLM)")

    hkcu_path = _read_path_hkcu() or ""
    paths = [p.strip() for p in hkcu_path.split(";") if p.strip()]
    paths.append(dir_path)
    hkcu_ok = _write_path_hkcu(";".join(paths))
    if hkcu_ok:
        logger.info(f"Added '{dir_path}' to user PATH (HKCU)")

    if hklm_ok or hkcu_ok:
        return True, "php.service.added_to_path"
    return False, "php.service.path_update_failed"


def _remove_path_env(dir_path: str) -> tuple[bool, str]:
    dir_path = dir_path.rstrip("\\")
    dir_norm = dir_path.lower()

    removed = False
    for scope, reader, writer in [("hklm", _read_path_hklm, _write_path_hklm), ("hkcu", _read_path_hkcu, _write_path_hkcu)]:
        current = reader()
        if current is None:
            continue
        paths = [p.strip() for p in current.split(";") if p.strip() and p.strip().rstrip("\\").lower() != dir_norm]
        new_path = ";".join(paths)
        if new_path != current:
            if writer(new_path):
                removed = True
                logger.info(f"Removed '{dir_path}' from {scope} PATH")

    if removed:
        return True, "php.service.removed_from_path"
    return True, "php.service.not_in_path"


def add_php_to_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(PHP_INSTALL_DIR, instance_name)
    if not os.path.exists(instance_dir):
        return False, "php.service.dir_not_found"
    return _add_path_env(instance_dir)


def remove_php_from_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(PHP_INSTALL_DIR, instance_name)
    return _remove_path_env(instance_dir)


def is_php_in_path(instance_name: str) -> bool:
    instance_dir = os.path.join(PHP_INSTALL_DIR, instance_name)
    return _find_dir_in_path(instance_dir) is not None


# --- Composer ---

def is_composer_installed() -> bool:
    return os.path.exists(os.path.join(COMPOSER_INSTALL_DIR, "composer.phar"))


def install_composer() -> tuple[bool, str]:
    logger.info("Starting Composer installation")

    if not os.path.exists(COMPOSER_PKG_PATH):
        return False, "php.service.composer_pkg_not_found"

    if is_composer_installed():
        return True, "php.service.composer_already_installed"

    try:
        os.makedirs(COMPOSER_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(COMPOSER_PKG_PATH, 'r') as zip_ref:
            zip_ref.extractall(COMPOSER_INSTALL_DIR)

        if not is_composer_installed():
            return False, "php.service.composer_install_failed"

        logger.info(f"Composer installed to '{COMPOSER_INSTALL_DIR}'")
        return True, "php.service.composer_install_success"

    except Exception as e:
        logger.error(f"Composer installation failed: {e}")
        if os.path.exists(COMPOSER_INSTALL_DIR):
            shutil.rmtree(COMPOSER_INSTALL_DIR)
        return False, str(e)


def uninstall_composer() -> tuple[bool, str]:
    logger.info("Attempting to uninstall Composer")

    if not os.path.exists(COMPOSER_INSTALL_DIR):
        return False, "php.service.composer_not_installed"

    remove_composer_from_path()

    try:
        shutil.rmtree(COMPOSER_INSTALL_DIR)
        logger.info("Composer uninstalled successfully")
        return True, "php.service.composer_uninstall_success"
    except OSError as e:
        logger.error(f"Failed to remove Composer directory: {e}")
        return False, "php.service.composer_remove_failed"


def add_composer_to_path() -> tuple[bool, str]:
    if not os.path.exists(COMPOSER_INSTALL_DIR):
        return False, "php.service.composer_not_installed"
    return _add_path_env(COMPOSER_INSTALL_DIR)


def remove_composer_from_path() -> tuple[bool, str]:
    return _remove_path_env(COMPOSER_INSTALL_DIR)


def is_composer_in_path() -> bool:
    return _find_dir_in_path(COMPOSER_INSTALL_DIR) is not None
