import os
import subprocess
import zipfile
import shutil
import json
import re
import winreg
from src.core.config import REDIS_PKG_DIR, REDIS_INSTALL_DIR
from src.utils.logger import setup_logger

logger = setup_logger("redis_service")


class RedisInstance:
    def __init__(self, name, version, port=6379, password="", service_name=""):
        self.name = name
        self.version = version
        self.port = port
        self.password = password
        self.install_dir = os.path.join(REDIS_INSTALL_DIR, self.name)
        self.bin_dir = self.install_dir
        self.redis_server_exe = os.path.join(self.install_dir, "redis-server.exe")
        self.redis_cli_exe = os.path.join(self.install_dir, "redis-cli.exe")
        self.redis_service_exe = os.path.join(self.install_dir, "RedisService.exe")
        self.redis_conf = self._detect_conf_file()
        self.meta_file = os.path.join(self.install_dir, "instance.json")
        self.service_name = service_name or self._generate_service_name()

    def _detect_conf_file(self) -> str:
        for conf_name in ["redis.conf", "redis.windows.conf"]:
            conf_path = os.path.join(self.install_dir, conf_name)
            if os.path.exists(conf_path):
                return conf_path
        return os.path.join(self.install_dir, "redis.conf")

    @property
    def has_redis_service_exe(self) -> bool:
        return os.path.exists(self.redis_service_exe)

    def _generate_service_name(self) -> str:
        version = self.version or ""
        version_short = version.split("-")[0].split(".")[0] if version else ""
        return f"Redis{version_short}"

    def save_metadata(self):
        meta = {
            "name": self.name,
            "version": self.version,
            "port": self.port,
            "password": self.password,
            "service_name": self.service_name,
        }
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f)

    @classmethod
    def load_from_metadata(cls, path: str):
        try:
            with open(os.path.join(path, "instance.json"), 'r', encoding='utf-8') as f:
                meta = json.load(f)
            return cls(
                name=meta['name'],
                version=meta['version'],
                port=meta.get('port', 6379),
                password=meta.get('password', ''),
                service_name=meta.get('service_name', ''),
            )
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


def _run_shell_command(cmd: str) -> tuple[bool, str]:
    try:
        logger.info(f"Running shell command: {cmd}")
        process = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if process.returncode == 0:
            logger.info(process.stdout)
            return True, process.stdout
        else:
            logger.error(f"Shell command failed: {cmd}")
            logger.error(f"Stderr: {process.stderr}")
            logger.error(f"Stdout: {process.stdout}")
            return False, process.stderr or process.stdout or f"Exit code: {process.returncode}"
    except Exception as e:
        logger.error(f"Shell command exception: {e}")
        return False, str(e)


def get_available_redis_packages() -> list[str]:
    if not os.path.exists(REDIS_PKG_DIR):
        os.makedirs(REDIS_PKG_DIR)
        return []
    packages = [
        f
        for f in os.listdir(REDIS_PKG_DIR)
        if f.endswith(".zip") and os.path.isfile(os.path.join(REDIS_PKG_DIR, f))
    ]
    return packages


def _extract_version(instance_name: str) -> str:
    parts = instance_name.split('-')
    for part in parts:
        if part and part[0].isdigit():
            return part
    return instance_name


def _make_service_name(instance_name: str) -> str:
    version = _extract_version(instance_name)
    version_short = version.split("-")[0].split(".")[0] if version else ""
    return f"Redis{version_short}"


def install_redis_instance(pkg_name: str, port: int = 6379, progress_callback=None) -> tuple[bool, str]:
    def _report(step_key: str, percent: int):
        if progress_callback:
            progress_callback(step_key, percent)

    instance_name = pkg_name.replace('.zip', '')
    service_name = _make_service_name(instance_name)
    logger.info(f"Starting installation for Redis instance '{instance_name}' (service: '{service_name}') from '{pkg_name}' on port {port}")

    zip_path = os.path.join(REDIS_PKG_DIR, pkg_name)
    instance = RedisInstance(name=instance_name, version=_extract_version(instance_name), port=port, service_name=service_name)

    if not os.path.exists(zip_path):
        return False, "redis.service.pkg_not_found"
    if os.path.exists(instance.install_dir):
        return False, "redis.service.dir_already_exists"

    try:
        logger.info(f"Extracting '{zip_path}' to '{instance.install_dir}'")
        _report("redis.install.step.extract", 30)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            extract_temp_dir = instance.install_dir + "_temp"
            zip_ref.extractall(extract_temp_dir)

            _report("redis.install.step.move", 60)
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

        if os.path.exists(instance.redis_conf):
            try:
                with open(instance.redis_conf, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                content = re.sub(r'^port\s+\d+', f'port {port}', content, flags=re.MULTILINE)
                with open(instance.redis_conf, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Updated port to {port} in {os.path.basename(instance.redis_conf)}")
            except Exception as e:
                logger.warning(f"Failed to update port in config: {e}")

        _report("redis.install.step.install_service", 80)
        service_installed = False
        if instance.has_redis_service_exe:
            success, msg = _run_command([
                instance.redis_service_exe, "install",
                "-c", instance.redis_conf,
                "--port", str(port),
                "--service-name", instance.service_name,
                "--start-mode", "manual",
            ])
            if success:
                logger.info(f"Redis service '{instance.service_name}' installed via RedisService.exe")
                service_installed = True
            else:
                logger.warning(f"RedisService.exe install failed: {msg}")

        if not service_installed:
            bin_path = f'\\"{instance.redis_server_exe}\\" \\"{instance.redis_conf}\\"'
            sc_create_cmd = f'sc create {instance.service_name} binPath= "{bin_path}" start= demand DisplayName= "Redis {instance.version}"'
            success, msg = _run_shell_command(sc_create_cmd)
            if success:
                logger.info(f"Redis service '{instance.service_name}' created via sc create")
                service_installed = True
            else:
                logger.warning(f"sc create failed: {msg}")

        if not service_installed:
            logger.warning("All service installation methods failed, Redis will run as a standalone process")

        _report("redis.install.step.save_metadata", 100)
        instance.save_metadata()

        logger.info(f"Installation successful for Redis instance '{instance_name}'")
        return True, "redis.service.install_success"

    except Exception as e:
        logger.error(f"Installation failed for Redis instance '{instance_name}': {e}")
        if os.path.exists(instance.install_dir):
            shutil.rmtree(instance.install_dir)
        return False, str(e)


def _get_service_name(instance_name: str) -> str:
    instances = get_installed_instances()
    for inst in instances:
        if inst.name == instance_name:
            return inst.service_name
    return _make_service_name(instance_name)


def uninstall_redis_instance(instance_name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to uninstall Redis instance '{instance_name}'")
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    if not os.path.exists(instance_dir):
        return False, "redis.service.dir_not_found"

    service_name = _get_service_name(instance_name)
    status = get_instance_status(instance_name)
    if status == "Running":
        stop_success, stop_msg = stop_redis_instance(instance_name)
        if not stop_success:
            return False, "redis.service.stop_before_uninstall_failed"

    sc_delete_success, sc_delete_msg = _run_command(["sc", "delete", service_name])
    if sc_delete_success:
        logger.info(f"Service '{service_name}' deleted via sc delete")
    else:
        logger.warning(f"Could not delete service '{service_name}' via sc delete: {sc_delete_msg}")
        redis_service_exe = os.path.join(instance_dir, "RedisService.exe")
        if os.path.exists(redis_service_exe):
            success, msg = _run_command([redis_service_exe, "uninstall", "--service-name", service_name])
            if success:
                logger.info(f"Service '{service_name}' uninstalled via RedisService.exe")
            else:
                logger.warning(f"RedisService.exe uninstall also failed: {msg}")

    _remove_path_env(instance_dir)

    try:
        shutil.rmtree(instance_dir)
        logger.info(f"Successfully removed Redis instance directory '{instance_dir}'")
        return True, "redis.service.uninstall_success"
    except OSError as e:
        logger.error(f"Failed to remove Redis instance directory '{instance_dir}': {e}")
        return False, "redis.service.remove_dir_failed"


def get_installed_instances() -> list[RedisInstance]:
    if not os.path.exists(REDIS_INSTALL_DIR):
        os.makedirs(REDIS_INSTALL_DIR)
        return []
    instances = []
    for dir_name in os.listdir(REDIS_INSTALL_DIR):
        path = os.path.join(REDIS_INSTALL_DIR, dir_name)
        if os.path.isdir(path):
            instance = RedisInstance.load_from_metadata(path)
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
        if is_redis_in_path(inst.name):
            in_path.append(inst.name)
    return in_path


def _get_instance_port(instance_name: str) -> int:
    instances = get_installed_instances()
    for inst in instances:
        if inst.name == instance_name:
            return inst.port
    return 6379


def _detect_conf_file(instance_dir: str) -> str:
    for conf_name in ["redis.conf", "redis.windows.conf"]:
        conf_path = os.path.join(instance_dir, conf_name)
        if os.path.exists(conf_path):
            return conf_path
    return os.path.join(instance_dir, "redis.conf")


def _is_redis_process_running(instance_name: str) -> bool:
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    redis_server_exe = os.path.join(instance_dir, "redis-server.exe")
    if not os.path.exists(redis_server_exe):
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq redis-server.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and "redis-server.exe" in result.stdout.lower():
            port = _get_instance_port(instance_name)
            instance = RedisInstance.load_from_metadata(instance_dir)
            cli_exe = os.path.join(instance_dir, "redis-cli.exe") if instance else None
            if cli_exe and os.path.exists(cli_exe):
                ping_result = subprocess.run(
                    [cli_exe, "-p", str(port), "ping"],
                    capture_output=True, text=True, encoding='gbk', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=3
                )
                if "PONG" in ping_result.stdout:
                    return True
            return True
        return False
    except Exception:
        return False


def get_instance_status(instance_name: str) -> str:
    service_name = _get_service_name(instance_name)
    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True, text=True, encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout
        if "STATE" in output and "RUNNING" in output:
            return "Running"
        elif "STATE" in output and "STOPPED" in output:
            return "Stopped"
        elif "1060" in result.stderr or "1060" in output:
            if _is_redis_process_running(instance_name):
                return "Running"
            return "Not Found"
        else:
            if _is_redis_process_running(instance_name):
                return "Running"
            return "Unknown"
    except subprocess.CalledProcessError as e:
        if "1060" in e.stderr:
            if _is_redis_process_running(instance_name):
                return "Running"
            return "Not Found"
        logger.error(f"Error checking status for '{service_name}': {e.stderr}")
        return "Error"
    except FileNotFoundError:
        logger.error("sc.exe not found")
        return "Error"


def start_redis_instance(instance_name: str) -> tuple[bool, str]:
    service_name = _get_service_name(instance_name)
    logger.info(f"Attempting to start Redis instance '{instance_name}' (service: '{service_name}')")
    status = get_instance_status(instance_name)
    if status == "Running":
        return True, "redis.service.already_running"

    success, msg = _run_command(["net", "start", service_name])
    if success:
        logger.info(f"Successfully started Redis service '{service_name}'")
        return True, "redis.service.start_success"

    logger.warning(f"net start failed for '{service_name}': {msg}, trying process start")

    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    redis_service_exe = os.path.join(instance_dir, "RedisService.exe")
    redis_server_exe = os.path.join(instance_dir, "redis-server.exe")
    redis_conf = _detect_conf_file(instance_dir)
    port = _get_instance_port(instance_name)

    if os.path.exists(redis_service_exe):
        try:
            subprocess.Popen(
                [redis_service_exe, "run", "-c", redis_conf, "--port", str(port)],
                cwd=instance_dir,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
            logger.info(f"Redis started via RedisService.exe for '{instance_name}'")
            import time
            time.sleep(1)
            if get_instance_status(instance_name) == "Running":
                return True, "redis.service.start_success"
        except Exception as e:
            logger.warning(f"RedisService.exe start failed: {e}")

    if os.path.exists(redis_server_exe) and os.path.exists(redis_conf):
        try:
            subprocess.Popen(
                [redis_server_exe, redis_conf],
                cwd=instance_dir,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
            logger.info(f"Redis process started for '{instance_name}'")
            import time
            time.sleep(1)
            if get_instance_status(instance_name) == "Running":
                return True, "redis.service.start_success"
            return True, "redis.service.start_success"
        except Exception as e:
            logger.error(f"Failed to start Redis process: {e}")
            return False, "redis.service.start_failed"

    logger.error(f"Failed to start Redis instance '{instance_name}'")
    return False, "redis.service.start_failed"


def stop_redis_instance(instance_name: str) -> tuple[bool, str]:
    service_name = _get_service_name(instance_name)
    logger.info(f"Attempting to stop Redis instance '{instance_name}' (service: '{service_name}')")
    status = get_instance_status(instance_name)
    if status == "Stopped":
        return True, "redis.service.already_stopped"

    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    redis_cli_exe = os.path.join(instance_dir, "redis-cli.exe")
    port = _get_instance_port(instance_name)

    if os.path.exists(redis_cli_exe):
        try:
            subprocess.run(
                [redis_cli_exe, "-p", str(port), "shutdown"],
                capture_output=True, text=True, encoding='gbk', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            import time
            time.sleep(0.5)
            if get_instance_status(instance_name) != "Running":
                logger.info(f"Redis stopped via redis-cli shutdown on port {port}")
                return True, "redis.service.stop_success"
            logger.warning(f"redis-cli shutdown sent but Redis still running")
        except Exception as e:
            logger.warning(f"redis-cli shutdown exception: {e}")

    success, msg = _run_command(["net", "stop", service_name])
    if success:
        logger.info(f"Successfully stopped Redis service '{service_name}' via net stop")
        return True, "redis.service.stop_success"

    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "redis-server.exe"],
            capture_output=True, text=True, encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        import time
        time.sleep(0.5)
        if get_instance_status(instance_name) != "Running":
            logger.info(f"Redis stopped via taskkill")
            return True, "redis.service.stop_success"
    except Exception as e:
        logger.error(f"Failed to stop Redis: {e}")

    if get_instance_status(instance_name) != "Running":
        return True, "redis.service.stop_success"

    return False, "redis.service.stop_failed"


def restart_redis_instance(instance_name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to restart Redis instance '{instance_name}'")
    status = get_instance_status(instance_name)

    if status == "Running":
        stop_success, stop_msg = stop_redis_instance(instance_name)
        if not stop_success:
            return False, "redis.service.stop_failed"

    start_success, start_msg = start_redis_instance(instance_name)
    if not start_success:
        return False, "redis.service.start_failed"

    return True, "redis.service.restart_success"


def update_redis_port(instance_name: str, new_port: int) -> tuple[bool, str]:
    logger.info(f"Updating port for Redis instance '{instance_name}' to {new_port}")
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    redis_conf = _detect_conf_file(instance_dir)
    meta_file = os.path.join(instance_dir, "instance.json")

    if not os.path.exists(redis_conf):
        return False, "redis.service.conf_not_found"

    try:
        with open(redis_conf, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        content = re.sub(r'^port\s+\d+', f'port {new_port}', content, flags=re.MULTILINE)

        with open(redis_conf, 'w', encoding='utf-8') as f:
            f.write(content)

        if os.path.exists(meta_file):
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            meta['port'] = new_port
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f)

        logger.info(f"Port updated for '{instance_name}' to {new_port}")
        return True, "redis.service.port_updated"
    except Exception as e:
        logger.error(f"Failed to update port: {e}")
        return False, "redis.service.port_update_failed"


# --- Environment Variable ---

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
        return True, "redis.service.already_in_path"

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
        return True, "redis.service.added_to_path"
    return False, "redis.service.path_update_failed"


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
        return True, "redis.service.removed_from_path"
    return True, "redis.service.not_in_path"


def add_redis_to_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    if not os.path.exists(instance_dir):
        return False, "redis.service.dir_not_found"
    return _add_path_env(instance_dir)


def remove_redis_from_path(instance_name: str) -> tuple[bool, str]:
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    return _remove_path_env(instance_dir)


def is_redis_in_path(instance_name: str) -> bool:
    instance_dir = os.path.join(REDIS_INSTALL_DIR, instance_name)
    return _find_dir_in_path(instance_dir) is not None
