import os
import subprocess
import zipfile
import shutil
import json
import winreg
from src.core.config import MYSQL_PKG_DIR, MYSQL_INSTALL_DIR
from src.utils.logger import setup_logger

logger = setup_logger("mysql_service")


class MySQLInstance:
    """Represents a single MySQL instance."""

    def __init__(self, name, version, port, password=""):
        self.name = name
        self.version = version
        self.port = port
        self.password = password
        self.install_dir = os.path.join(MYSQL_INSTALL_DIR, self.name)
        self.data_dir = os.path.join(self.install_dir, "data")
        self.bin_dir = os.path.join(self.install_dir, "bin")
        self.mysqld_exe = os.path.join(self.bin_dir, "mysqld.exe")
        self.mysql_exe = os.path.join(self.bin_dir, "mysql.exe")
        self.my_ini = os.path.join(self.install_dir, "my.ini")
        self.log_file = os.path.join(self.install_dir, "error.log")
        self.meta_file = os.path.join(self.install_dir, "instance.json")

    def save_metadata(self):
        """Saves instance metadata to a file."""
        meta = {"name": self.name, "version": self.version, "port": self.port, "password": self.password}
        with open(self.meta_file, 'w') as f:
            json.dump(meta, f)

    @classmethod
    def load_from_metadata(cls, path: str):
        """Loads an instance from its metadata file."""
        try:
            with open(os.path.join(path, "instance.json"), 'r') as f:
                meta = json.load(f)
            return cls(name=meta['name'], version=meta['version'], port=meta['port'], password=meta.get('password', ''))
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

# --- MySQL Installation ---

def get_available_mysql_packages() -> list[str]:
    """Scans for available MySQL installation packages."""
    if not os.path.exists(MYSQL_PKG_DIR):
        os.makedirs(MYSQL_PKG_DIR)
        return []
    
    packages = [
        f
        for f in os.listdir(MYSQL_PKG_DIR)
        if f.endswith(".zip") and os.path.isfile(os.path.join(MYSQL_PKG_DIR, f))
    ]
    return packages

def install_mysql_instance(pkg_name: str, port: int, progress_callback=None) -> tuple[bool, str]:
    """Installs a new MySQL instance from a package.
    
    progress_callback: optional callable(step_key: str, percent: int) for UI updates.
    """
    def _report(step_key: str, percent: int):
        if progress_callback:
            progress_callback(step_key, percent)

    instance_name = pkg_name.replace('.zip', '')
    logger.info(f"Starting installation for instance '{instance_name}' from '{pkg_name}' on port {port}")

    zip_path = os.path.join(MYSQL_PKG_DIR, pkg_name)
    template_path = os.path.join(MYSQL_PKG_DIR, "my.ini.example")
    instance = MySQLInstance(name=instance_name, version=instance_name.split('-')[1], port=port)

    if not os.path.exists(zip_path):
        return False, "mysql.service.pkg_not_found"
    if not os.path.exists(template_path):
        return False, "mysql.service.template_not_found"
    if os.path.exists(instance.install_dir):
        return False, "mysql.service.dir_already_exists"

    try:
        logger.info(f"Extracting '{zip_path}' to '{instance.install_dir}'")
        _report("mysql.install.step.extract", 10)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            extract_temp_dir = instance.install_dir + "_temp"
            zip_ref.extractall(extract_temp_dir)

            _report("mysql.install.step.move", 30)
            extracted_folder = os.path.join(extract_temp_dir, os.listdir(extract_temp_dir)[0])
            os.makedirs(instance.install_dir, exist_ok=True)
            for item in os.listdir(extracted_folder):
                shutil.move(os.path.join(extracted_folder, item), instance.install_dir)
            shutil.rmtree(extract_temp_dir)

        logger.info(f"Generating my.ini for '{instance.name}'")
        _report("mysql.install.step.config", 50)
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        config_content = template_content.replace("{BASEDIR}", instance.install_dir.replace('\\', '/')) \
                                         .replace("{DATADIR}", instance.data_dir.replace('\\', '/')) \
                                         .replace("{LOGFILE}", instance.log_file.replace('\\', '/')) \
                                         .replace("port=3306", f"port={instance.port}")

        with open(instance.my_ini, 'w', encoding='utf-8') as f:
            f.write(config_content)

        logger.info(f"Initializing database for '{instance.name}'")
        _report("mysql.install.step.init_db", 70)
        success, msg = _run_command([instance.mysqld_exe, "--initialize-insecure", f"--basedir={instance.install_dir}", f"--datadir={instance.data_dir}"])
        if not success:
            raise Exception("mysql.service.init_db_failed")

        logger.info(f"Installing service for '{instance.name}'")
        _report("mysql.install.step.install_service", 90)
        success, msg = _run_command([instance.mysqld_exe, "--install", instance.name, f"--defaults-file={instance.my_ini}"])
        if not success:
            raise Exception("mysql.service.install_svc_failed")

        service_status = get_instance_status(instance.name)
        if service_status == "Not Found":
            raise Exception("mysql.service.service_not_registered")

        sc_success, sc_msg = _run_command(["sc", "config", instance.name, "start=demand"])
        if sc_success:
            logger.info(f"Service '{instance.name}' set to manual start")
        else:
            logger.warning(f"Failed to set service '{instance.name}' to manual start: {sc_msg}")

        _report("mysql.install.step.save_metadata", 100)
        instance.save_metadata()

        logger.info(f"Installation successful for instance '{instance.name}'")
        return True, "mysql.service.install_success"

    except Exception as e:
        logger.error(f"Installation failed for instance '{instance.name}': {e}")
        if os.path.exists(instance.install_dir):
            shutil.rmtree(instance.install_dir)
        return False, str(e)


def uninstall_mysql_instance(instance_name: str) -> tuple[bool, str]:
    """Uninstalls a MySQL instance."""
    logger.info(f"Attempting to uninstall instance '{instance_name}'")
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    if not os.path.exists(instance_dir):
        return False, "mysql.service.dir_not_found"

    status = get_instance_status(instance_name)
    if status == "Running":
        stop_success, stop_msg = stop_mysql_instance(instance_name)
        if not stop_success:
            return False, "mysql.service.stop_before_uninstall_failed"

    mysqld_exe = os.path.join(instance_dir, "bin", "mysqld.exe")
    if os.path.exists(mysqld_exe):
        success, msg = _run_command([mysqld_exe, "--remove", instance_name])
        if not success and "The specified service does not exist" not in msg:
            logger.warning(f"Could not remove service '{instance_name}'. It might have already been removed. Error: {msg}")

    bin_dir = os.path.join(instance_dir, "bin")
    _remove_path_env(bin_dir)

    try:
        shutil.rmtree(instance_dir)
        logger.info(f"Successfully removed instance directory '{instance_dir}'")
        return True, "mysql.service.uninstall_success"
    except OSError as e:
        logger.error(f"Failed to remove instance directory '{instance_dir}': {e}")
        return False, "mysql.service.remove_dir_failed"

# --- MySQL Start/Stop ---

def get_installed_instances() -> list[MySQLInstance]:
    """Gets a list of all installed MySQL instances."""
    if not os.path.exists(MYSQL_INSTALL_DIR):
        os.makedirs(MYSQL_INSTALL_DIR)
        return []

    instances = []
    for dir_name in os.listdir(MYSQL_INSTALL_DIR):
        path = os.path.join(MYSQL_INSTALL_DIR, dir_name)
        if os.path.isdir(path):
            instance = MySQLInstance.load_from_metadata(path)
            if instance:
                instances.append(instance)
    return instances


def get_running_instances() -> list[str]:
    running = []
    for inst in get_installed_instances():
        if get_instance_status(inst.name) == "Running":
            running.append(inst.name)
    return running

def get_instances_in_path() -> list[str]:
    in_path = []
    for inst in get_installed_instances():
        if is_mysql_in_path(inst.name):
            in_path.append(inst.name)
    return in_path

def get_instance_status(instance_name: str) -> str:
    """Checks the status of a MySQL service. Returns 'Running', 'Stopped', or 'Not Found'."""
    try:
        result = subprocess.run(
            ["sc", "query", instance_name],
            capture_output=True, text=True, encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout
        if "STATE" in output and "RUNNING" in output:
            return "Running"
        elif "STATE" in output and "STOPPED" in output:
            return "Stopped"
        # Case where service exists but is in a transient state (e.g., START_PENDING)
        elif "1060" in result.stderr:
            return "Not Found"
        else:
            # Fallback for other states, can be refined if needed
            return "Unknown"
    except subprocess.CalledProcessError as e:
        if "1060" in e.stderr:  # Error code for "The specified service does not exist"
            return "Not Found"
        logger.error(f"Error checking status for '{instance_name}': {e.stderr}")
        return "Error"
    except FileNotFoundError:
        logger.error("sc.exe not found. Is it in the system's PATH?")
        return "Error"


def start_mysql_instance(instance_name: str) -> tuple[bool, str]:
    """Starts a specific MySQL instance service."""
    logger.info(f"Attempting to start MySQL instance service: '{instance_name}'")
    status = get_instance_status(instance_name)
    if status == "Running":
        return True, "mysql.service.already_running"
    if status == "Not Found":
        return False, "mysql.service.not_found"

    success, msg = _run_command(["net", "start", instance_name])
    if success:
        logger.info(f"Successfully started service '{instance_name}'.")
        return True, "mysql.service.start_success"
    else:
        logger.error(f"Failed to start service '{instance_name}': {msg}")
        return False, "mysql.service.start_failed"


def stop_mysql_instance(instance_name: str) -> tuple[bool, str]:
    """Stops a specific MySQL instance service."""
    logger.info(f"Attempting to stop MySQL instance service: '{instance_name}'")
    status = get_instance_status(instance_name)
    if status == "Stopped":
        return True, "mysql.service.already_stopped"
    if status == "Not Found":
        return False, "mysql.service.not_found"

    success, msg = _run_command(["net", "stop", instance_name])
    if success:
        logger.info(f"Successfully stopped service '{instance_name}'.")
        return True, "mysql.service.stop_success"
    else:
        logger.error(f"Failed to stop service '{instance_name}': {msg}")
        return False, "mysql.service.stop_failed"


def restart_mysql_instance(instance_name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to restart MySQL instance service: '{instance_name}'")
    status = get_instance_status(instance_name)
    if status == "Not Found":
        return False, "mysql.service.not_found"

    if status == "Running":
        stop_success, stop_msg = stop_mysql_instance(instance_name)
        if not stop_success:
            return False, "mysql.service.stop_failed"

    start_success, start_msg = start_mysql_instance(instance_name)
    if not start_success:
        return False, "mysql.service.start_failed"

    return True, "mysql.service.restart_success"


# --- MySQL Configuration ---

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
        return True, "mysql.service.already_in_path"

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
        return True, "mysql.service.added_to_path"
    return False, "mysql.service.path_update_failed"

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
        return True, "mysql.service.removed_from_path"
    return True, "mysql.service.not_in_path"

def is_path_env_set(dir_path: str) -> bool:
    return _find_dir_in_path(dir_path) is not None

def update_mysql_port(instance_name: str, new_port: int) -> tuple[bool, str]:
    logger.info(f"Updating port for instance '{instance_name}' to {new_port}")
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    my_ini = os.path.join(instance_dir, "my.ini")
    meta_file = os.path.join(instance_dir, "instance.json")

    if not os.path.exists(my_ini):
        return False, "mysql.service.myini_not_found"

    try:
        with open(my_ini, 'r', encoding='utf-8') as f:
            content = f.read()

        import re
        content = re.sub(r'port=\d+', f'port={new_port}', content)

        with open(my_ini, 'w', encoding='utf-8') as f:
            f.write(content)

        if os.path.exists(meta_file):
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            meta['port'] = new_port
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f)

        logger.info(f"Port updated for '{instance_name}' to {new_port}")
        return True, "mysql.service.port_updated"
    except Exception as e:
        logger.error(f"Failed to update port: {e}")
        return False, "mysql.service.port_update_failed"

def update_mysql_root_password(instance_name: str, new_password: str, current_password: str = "") -> tuple[bool, str]:
    logger.info(f"Updating root password for instance '{instance_name}'")
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    mysql_exe = os.path.join(instance_dir, "bin", "mysql.exe")
    my_ini = os.path.join(instance_dir, "my.ini")

    if not os.path.exists(mysql_exe):
        return False, "mysql.service.mysqld_not_found"

    status = get_instance_status(instance_name)
    if status != "Running":
        return False, "mysql.service.must_running_to_change_pwd"

    try:
        cmd = [mysql_exe, f"--defaults-file={my_ini}", "-u", "root"]
        if current_password:
            cmd.append(f"-p{current_password}")
        cmd.extend(["-e", f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{new_password}';"])
        success, msg = _run_command(cmd)
        if success:
            logger.info(f"Root password updated for '{instance_name}'")
            meta_file = os.path.join(instance_dir, "instance.json")
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    meta['password'] = new_password
                    with open(meta_file, 'w', encoding='utf-8') as f:
                        json.dump(meta, f)
                except Exception as e:
                    logger.warning(f"Failed to save password to metadata: {e}")
            return True, "mysql.service.pwd_updated"
        else:
            return False, "mysql.service.pwd_update_failed"
    except Exception as e:
        logger.error(f"Failed to update root password: {e}")
        return False, "mysql.service.pwd_update_failed"

def add_mysql_to_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    bin_dir = os.path.join(instance_dir, "bin")
    if not os.path.exists(bin_dir):
        return False, "mysql.service.bin_not_found"
    return _add_path_env(bin_dir)

def remove_mysql_from_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    bin_dir = os.path.join(instance_dir, "bin")
    return _remove_path_env(bin_dir)

def is_mysql_in_path(instance_name: str) -> bool:
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    bin_dir = os.path.join(instance_dir, "bin")
    return is_path_env_set(bin_dir)

def get_mysql_instance_config(instance_name: str) -> dict:
    logger.info(f"Getting configuration for MySQL instance '{instance_name}'")
    instance_dir = os.path.join(MYSQL_INSTALL_DIR, instance_name)
    my_ini = os.path.join(instance_dir, "my.ini")
    config = {}
    if os.path.exists(my_ini):
        try:
            with open(my_ini, 'r', encoding='utf-8') as f:
                content = f.read()
            import re
            port_match = re.search(r'port=(\d+)', content)
            if port_match:
                config['port'] = int(port_match.group(1))
        except Exception:
            pass
    config['path_env'] = is_mysql_in_path(instance_name)
    return config
