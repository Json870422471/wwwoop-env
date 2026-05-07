import os
import subprocess
import json
import re
import winreg
import zipfile
import shutil
from src.core.config import JAVA_PKG_DIR, JAVA_INSTALL_DIR, MAVEN_PKG_PATH, MAVEN_SETTINGS_TEMPLATE, MAVEN_INSTALL_DIR
from src.utils.logger import setup_logger

logger = setup_logger("java_service")


class JavaInstance:
    def __init__(self, name, version, install_dir=""):
        self.name = name
        self.version = version
        self.install_dir = install_dir
        self.bin_dir = os.path.join(self.install_dir, "bin") if self.install_dir else ""
        self.java_exe = os.path.join(self.bin_dir, "java.exe") if self.bin_dir else ""
        self.javac_exe = os.path.join(self.bin_dir, "javac.exe") if self.bin_dir else ""
        self.meta_file = os.path.join(JAVA_INSTALL_DIR, f"{self.name}.json")

    def save_metadata(self):
        meta = {
            "name": self.name,
            "version": self.version,
            "install_dir": self.install_dir,
        }
        os.makedirs(JAVA_INSTALL_DIR, exist_ok=True)
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_metadata(cls, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            return cls(
                name=meta['name'],
                version=meta['version'],
                install_dir=meta.get('install_dir', '')
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
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command)}")
        logger.error(f"Stderr: {e.stderr}")
        logger.error(f"Stdout: {e.stdout}")
        return False, e.stderr or e.stdout or str(e)
    except FileNotFoundError as e:
        logger.error(f"Command not found: {e}")
        return False, str(e)


def _run_shell_command(command: str, cwd: str | None = None) -> tuple[bool, str]:
    try:
        logger.info(f"Running shell command: {command}")
        process = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True,
            encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True
        )
        if process.returncode == 0:
            return True, process.stdout
        else:
            return False, process.stderr or process.stdout or f"Exit code: {process.returncode}"
    except Exception as e:
        logger.error(f"Shell command failed: {e}")
        return False, str(e)


_HKLM_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
_HKCU_ENV = r"Environment"


def _read_env_var_hklm(name: str) -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None


def _read_env_var_hkcu(name: str) -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None


def _write_env_var_hklm(name: str, value: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKLM env var '{name}': {e}")
        return False


def _write_env_var_hkcu(name: str, value: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKCU env var '{name}': {e}")
        return False


def _delete_env_var_hklm(name: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to delete HKLM env var '{name}': {e}")
        return False


def _delete_env_var_hkcu(name: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to delete HKCU env var '{name}': {e}")
        return False


def _write_env_var(name: str, value: str) -> bool:
    hklm_ok = _write_env_var_hklm(name, value)
    hkcu_ok = _write_env_var_hkcu(name, value)
    if hklm_ok:
        logger.info(f"Set {name}={value} in HKLM")
    if hkcu_ok:
        logger.info(f"Set {name}={value} in HKCU")
    return hklm_ok or hkcu_ok


def _delete_env_var(name: str) -> bool:
    hklm_ok = _delete_env_var_hklm(name)
    hkcu_ok = _delete_env_var_hkcu(name)
    if hklm_ok:
        logger.info(f"Deleted {name} from HKLM")
    if hkcu_ok:
        logger.info(f"Deleted {name} from HKCU")
    return hklm_ok or hkcu_ok


def _read_env_var(name: str) -> str | None:
    value = _read_env_var_hklm(name)
    if value is not None:
        return value
    return _read_env_var_hkcu(name)


def _notify_env_change():
    try:
        from ctypes import windll
        windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
    except Exception:
        pass


def _read_path_hklm() -> str | None:
    return _read_env_var_hklm("Path")


def _read_path_hkcu() -> str | None:
    return _read_env_var_hkcu("Path")


def _write_path_hklm(new_path: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HKLM_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKLM PATH: {e}")
        return False


def _write_path_hkcu(new_path: str) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _HKCU_ENV, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        _notify_env_change()
        return True
    except WindowsError as e:
        logger.error(f"Failed to set HKCU PATH: {e}")
        return False


def _find_in_path(dir_path: str) -> bool:
    dir_norm = dir_path.rstrip("\\").lower()
    for reader in [_read_path_hklm, _read_path_hkcu]:
        current = reader()
        if current is None:
            continue
        for p in current.split(";"):
            if p.strip().rstrip("\\").lower() == dir_norm:
                return True
    return False


def _add_to_path(dir_path: str) -> tuple[bool, str]:
    dir_path = dir_path.rstrip("\\")
    if _find_in_path(dir_path):
        return True, "java.service.already_in_path"

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
        return True, "java.service.added_to_path"
    return False, "java.service.path_update_failed"


def _remove_from_path(dir_path: str) -> tuple[bool, str]:
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
        return True, "java.service.removed_from_path"
    return True, "java.service.not_in_path"


def _extract_version_from_filename(filename: str) -> str:
    name = filename.lower()
    if "jdk-21" in name or "jdk21" in name:
        return "21"
    elif "jdk-17" in name or "jdk17" in name:
        return "17"
    elif "jdk-11" in name or "jdk11" in name:
        return "11"
    elif "jdk-8" in name or "jdk8" in name or "jdk-8u" in name:
        return "1.8"
    match = re.search(r'jdk[-_]?(\d+)', name)
    if match:
        v = match.group(1)
        if v == "8":
            return "1.8"
        return v
    return "unknown"


def _generate_instance_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    return name


def _detect_jdk_install_dir(instance_name: str) -> str | None:
    instance = get_installed_instance(instance_name)
    if instance and instance.install_dir and os.path.exists(instance.java_exe):
        return instance.install_dir

    version = instance.version if instance else "unknown"

    common_paths = []
    if version == "1.8":
        common_paths = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Java", "jdk1.8.0_301"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Java", "jdk-1.8"),
        ]
    elif version == "21":
        common_paths = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Java", "jdk-21"),
        ]
    else:
        common_paths = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Java", f"jdk-{version}"),
        ]

    for p in common_paths:
        java_exe = os.path.join(p, "bin", "java.exe")
        if os.path.exists(java_exe):
            return p

    return None


def _scan_registry_jdks() -> list[dict]:
    jdks = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        idx = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, idx)
                subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                try:
                    java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                    jdks.append({"version": subkey_name, "install_dir": java_home})
                except WindowsError:
                    pass
                winreg.CloseKey(subkey)
                idx += 1
            except WindowsError:
                break
        winreg.CloseKey(key)
    except WindowsError:
        pass

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JDK", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        idx = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, idx)
                subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                try:
                    java_home, _ = winreg.QueryValueEx(subkey, "JavaHome")
                    jdks.append({"version": subkey_name, "install_dir": java_home})
                except WindowsError:
                    pass
                winreg.CloseKey(subkey)
                idx += 1
            except WindowsError:
                break
        winreg.CloseKey(key)
    except WindowsError:
        pass

    return jdks


def get_available_java_packages() -> list[str]:
    if not os.path.exists(JAVA_PKG_DIR):
        os.makedirs(JAVA_PKG_DIR, exist_ok=True)
        return []

    packages = []
    for f in os.listdir(JAVA_PKG_DIR):
        full_path = os.path.join(JAVA_PKG_DIR, f)
        if os.path.isfile(full_path) and (f.endswith(".exe") or f.endswith(".zip")):
            packages.append(f)
    return sorted(packages)


def get_installed_instances() -> list[JavaInstance]:
    if not os.path.exists(JAVA_INSTALL_DIR):
        os.makedirs(JAVA_INSTALL_DIR, exist_ok=True)
        return []

    instances = []
    for f in os.listdir(JAVA_INSTALL_DIR):
        if f.endswith(".json"):
            path = os.path.join(JAVA_INSTALL_DIR, f)
            instance = JavaInstance.load_from_metadata(path)
            if instance:
                instances.append(instance)
    return instances


def get_installed_instance(name: str) -> JavaInstance | None:
    for inst in get_installed_instances():
        if inst.name == name:
            return inst
    return None


def install_java_instance(pkg_name: str, progress_callback=None) -> tuple[bool, str]:
    def _report(step_key: str, percent: int):
        if progress_callback:
            progress_callback(step_key, percent)

    instance_name = _generate_instance_name(pkg_name)
    version = _extract_version_from_filename(pkg_name)
    pkg_path = os.path.join(JAVA_PKG_DIR, pkg_name)

    logger.info(f"Starting JDK installation for '{instance_name}' (version {version}) from '{pkg_name}'")

    if not os.path.exists(pkg_path):
        return False, "java.service.pkg_not_found"

    existing = get_installed_instance(instance_name)
    if existing:
        return False, "java.service.already_installed"

    _report("java.install.step.launch_installer", 20)

    try:
        logger.info(f"Launching JDK installer: {pkg_path}")
        process = subprocess.run(
            [pkg_path],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if not subprocess.CREATE_NEW_CONSOLE else 0,
            timeout=1800
        )
        logger.info(f"JDK installer exited with code: {process.returncode}")
        if process.returncode != 0:
            logger.warning(f"JDK installer exited with non-zero code: {process.returncode}, likely cancelled by user")
            return False, "java.service.install_cancelled"
    except subprocess.TimeoutExpired:
        logger.error("JDK installer timed out")
        return False, "java.service.install_timeout"
    except Exception as e:
        logger.error(f"Failed to launch JDK installer: {e}")
        return False, "java.service.install_failed"

    _report("java.install.step.detect_install", 60)

    install_dir = None
    registry_jdks = _scan_registry_jdks()
    for jdk in registry_jdks:
        jdk_version = jdk["version"]
        if version == "1.8" and ("1.8" in jdk_version or "8" in jdk_version):
            install_dir = jdk["install_dir"]
            break
        elif version != "1.8" and version in jdk_version:
            install_dir = jdk["install_dir"]
            break

    if not install_dir:
        for jdk in registry_jdks:
            java_exe = os.path.join(jdk["install_dir"], "bin", "java.exe")
            if os.path.exists(java_exe):
                already_registered = any(
                    inst.install_dir == jdk["install_dir"]
                    for inst in get_installed_instances()
                )
                if not already_registered:
                    install_dir = jdk["install_dir"]
                    version = jdk["version"]
                    break

    if not install_dir:
        logger.warning("Could not auto-detect JDK install directory after installation")
        instance = JavaInstance(name=instance_name, version=version, install_dir="")
        instance.save_metadata()
        _report("java.install.step.save_metadata", 100)
        return True, "java.service.install_success_manual"

    java_exe = os.path.join(install_dir, "bin", "java.exe")
    if not os.path.exists(java_exe):
        logger.warning(f"java.exe not found at {java_exe}")
        instance = JavaInstance(name=instance_name, version=version, install_dir=install_dir)
        instance.save_metadata()
        _report("java.install.step.save_metadata", 100)
        return True, "java.service.install_success_manual"

    _report("java.install.step.save_metadata", 80)

    instance = JavaInstance(name=instance_name, version=version, install_dir=install_dir)
    instance.save_metadata()

    _report("java.install.step.complete", 100)
    logger.info(f"JDK installation successful: {instance_name} at {install_dir}")
    return True, "java.service.install_success"


def _find_all_java_uninstallers(install_dir: str, version: str) -> list[str]:
    if not install_dir:
        return []

    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    results = []
    seen_cmds = set()

    for root_key in uninstall_keys:
        for access_flag in [winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY]:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_key, 0, access_flag)
                idx = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, idx)
                        subkey = winreg.OpenKey(key, subkey_name, 0, access_flag)
                        matched = False

                        try:
                            location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                            if location and location.rstrip("\\").lower() == install_dir.rstrip("\\").lower():
                                matched = True
                        except WindowsError:
                            pass

                        if not matched:
                            try:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if display_name:
                                    name_lower = display_name.lower()
                                    is_jdk = "jdk" in name_lower and "java" in name_lower
                                    is_jre = "jre" in name_lower and "java" in name_lower
                                    is_update = "update" in name_lower and "java" in name_lower
                                    if is_jdk or is_jre or is_update:
                                        try:
                                            location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                            if location and install_dir.rstrip("\\").lower() in location.rstrip("\\").lower():
                                                matched = True
                                        except WindowsError:
                                            pass

                                        if not matched and version == "1.8":
                                            try:
                                                location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                                if location:
                                                    loc_lower = location.lower()
                                                    if "java" in loc_lower and ("jre" in loc_lower or "jdk1.8" in loc_lower or "jdk-1.8" in loc_lower):
                                                        matched = True
                                            except WindowsError:
                                                pass
                            except WindowsError:
                                pass

                        if matched:
                            try:
                                uninstall_cmd, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                if uninstall_cmd and uninstall_cmd not in seen_cmds:
                                    seen_cmds.add(uninstall_cmd)
                                    results.append(uninstall_cmd)
                            except WindowsError:
                                pass

                        winreg.CloseKey(subkey)
                        idx += 1
                    except WindowsError:
                        break
                winreg.CloseKey(key)
            except WindowsError:
                continue

    return results


def uninstall_java_instance(instance_name: str) -> tuple[bool, str]:
    logger.info(f"Attempting to uninstall JDK instance '{instance_name}'")
    instance = get_installed_instance(instance_name)
    if not instance:
        return False, "java.service.not_installed"

    uninstaller_results = []
    if instance.install_dir:
        uninstall_cmds = _find_all_java_uninstallers(instance.install_dir, instance.version)
        for uninstall_cmd in uninstall_cmds:
            logger.info(f"Found Java uninstaller: {uninstall_cmd}")
            try:
                result = subprocess.run(
                    uninstall_cmd, shell=True,
                    timeout=600
                )
                if result.returncode == 0:
                    uninstaller_results.append(True)
                    logger.info("Java uninstaller executed successfully")
                else:
                    uninstaller_results.append(False)
                    logger.warning(f"Java uninstaller exited with code: {result.returncode}")
            except subprocess.TimeoutExpired:
                uninstaller_results.append(False)
                logger.warning("Java uninstaller timed out")
            except Exception as e:
                uninstaller_results.append(False)
                logger.warning(f"Failed to run Java uninstaller: {e}")

    if uninstaller_results and not all(uninstaller_results):
        if not any(uninstaller_results):
            return False, "java.service.uninstall_cancelled"
        return False, "java.service.uninstall_partial"

    current_java_home = _read_env_var("JAVA_HOME")
    if current_java_home and instance.install_dir:
        if current_java_home.rstrip("\\").lower() == instance.install_dir.rstrip("\\").lower():
            _delete_env_var("JAVA_HOME")
            logger.info("Removed JAVA_HOME (pointed to this instance)")

    _clean_jdk_paths_from_path()

    meta_file = os.path.join(JAVA_INSTALL_DIR, f"{instance_name}.json")
    if os.path.exists(meta_file):
        os.remove(meta_file)
        logger.info(f"Removed metadata file: {meta_file}")

    if uninstaller_results:
        return True, "java.service.uninstall_with_jdk_removed"
    return True, "java.service.uninstall_success"


def is_java_env_configured(instance_name: str) -> bool:
    instance = get_installed_instance(instance_name)
    if not instance or not instance.install_dir:
        return False
    java_home = _read_env_var("JAVA_HOME")
    if not java_home:
        return False
    return java_home.rstrip("\\").lower() == instance.install_dir.rstrip("\\").lower()


def get_instances_in_path() -> list[str]:
    in_path = []
    for inst in get_installed_instances():
        if is_java_env_configured(inst.name):
            in_path.append(inst.name)
    return in_path


def _clean_jdk_paths_from_path():
    jdk_keywords = ["\\java\\", "\\jdk", "java_home", "javapath"]
    for scope, reader, writer in [("hklm", _read_path_hklm, _write_path_hklm), ("hkcu", _read_path_hkcu, _write_path_hkcu)]:
        current = reader()
        if current is None:
            continue
        paths = [p.strip() for p in current.split(";") if p.strip()]
        cleaned = []
        changed = False
        for p in paths:
            p_lower = p.lower()
            should_remove = False
            for kw in jdk_keywords:
                if kw in p_lower:
                    should_remove = True
                    break
            if should_remove:
                logger.info(f"Removing JDK-related path from {scope} PATH: {p}")
                changed = True
            else:
                cleaned.append(p)
        if changed:
            writer(";".join(cleaned))


def configure_java_env(instance_name: str) -> tuple[bool, str]:
    instance = get_installed_instance(instance_name)
    if not instance:
        return False, "java.service.not_installed"
    if not instance.install_dir or not os.path.exists(instance.java_exe):
        return False, "java.service.install_dir_not_found"

    _clean_jdk_paths_from_path()

    _write_env_var("JAVA_HOME", instance.install_dir)
    logger.info(f"Set JAVA_HOME={instance.install_dir}")

    bin_path = "%JAVA_HOME%\\bin"
    if not _find_in_path(bin_path):
        _add_to_path(bin_path)
        logger.info(f"Added {bin_path} to PATH")

    return True, "java.service.env_configured"


def remove_java_env(instance_name: str) -> tuple[bool, str]:
    instance = get_installed_instance(instance_name)
    if not instance:
        return False, "java.service.not_installed"

    if is_java_env_configured(instance_name):
        _delete_env_var("JAVA_HOME")
        logger.info("Removed JAVA_HOME")

    _clean_jdk_paths_from_path()

    return True, "java.service.env_removed"


def get_java_version(instance_name: str) -> str | None:
    instance = get_installed_instance(instance_name)
    if not instance or not instance.install_dir:
        return None
    java_exe = os.path.join(instance.install_dir, "bin", "java.exe")
    if not os.path.exists(java_exe):
        return None
    try:
        result = subprocess.run(
            [java_exe, "-version"],
            capture_output=True, text=True,
            encoding='gbk', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10
        )
        output = result.stderr or result.stdout
        match = re.search(r'"(\d+[.\d]*)"', output)
        if match:
            return match.group(1)
    except Exception as e:
        logger.error(f"Failed to get Java version: {e}")
    return None


def get_suggested_install_dir(pkg_name: str) -> str:
    instance_name = _generate_instance_name(pkg_name)
    return os.path.join(JAVA_INSTALL_DIR, instance_name)


def _find_maven_bin_dir() -> str | None:
    if not os.path.exists(MAVEN_INSTALL_DIR):
        return None
    for entry in os.listdir(MAVEN_INSTALL_DIR):
        bin_dir = os.path.join(MAVEN_INSTALL_DIR, entry, "bin")
        if os.path.isdir(bin_dir) and os.path.exists(os.path.join(bin_dir, "mvn.cmd")):
            return os.path.join(MAVEN_INSTALL_DIR, entry)
    return None


def is_maven_installed() -> bool:
    return _find_maven_bin_dir() is not None


def get_maven_install_dir() -> str | None:
    return _find_maven_bin_dir()


def install_maven(local_repo: str, use_aliyun_mirror: bool) -> tuple[bool, str]:
    logger.info("Starting Maven installation")

    if not os.path.exists(MAVEN_PKG_PATH):
        return False, "java.service.maven_pkg_not_found"

    if is_maven_installed():
        return False, "java.service.maven_already_installed"

    if not local_repo.strip():
        return False, "java.service.maven_repo_required"

    try:
        os.makedirs(MAVEN_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(MAVEN_PKG_PATH, 'r') as zip_ref:
            zip_ref.extractall(MAVEN_INSTALL_DIR)

        maven_dir = _find_maven_bin_dir()
        if not maven_dir:
            shutil.rmtree(MAVEN_INSTALL_DIR, ignore_errors=True)
            return False, "java.service.maven_install_failed"

        conf_dir = os.path.join(maven_dir, "conf")
        settings_target = os.path.join(conf_dir, "settings.xml")

        if os.path.exists(MAVEN_SETTINGS_TEMPLATE):
            with open(MAVEN_SETTINGS_TEMPLATE, 'r', encoding='utf-8') as f:
                content = f.read()

            local_repo_xml = f'  <localRepository>{local_repo}</localRepository>'
            content = content.replace('{{localRepository}}', local_repo_xml)

            if use_aliyun_mirror:
                mirror_xml = '''    <mirror>
      <id>nexus-aliyun</id>
      <mirrorOf>central</mirrorOf>
      <name>Nexus aliyun</name>
      <url>http://maven.aliyun.com/nexus/content/groups/public</url>
    </mirror>
'''
                content = content.replace('{{mirrors}}', mirror_xml)
            else:
                content = content.replace('{{mirrors}}', '')

            with open(settings_target, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Maven settings.xml configured: localRepo={local_repo}, aliyun={use_aliyun_mirror}")

        logger.info(f"Maven installed to '{maven_dir}'")
        return True, "java.service.maven_install_success"

    except Exception as e:
        logger.error(f"Maven installation failed: {e}")
        if os.path.exists(MAVEN_INSTALL_DIR):
            shutil.rmtree(MAVEN_INSTALL_DIR, ignore_errors=True)
        return False, "java.service.maven_install_failed"


def uninstall_maven() -> tuple[bool, str]:
    logger.info("Attempting to uninstall Maven")

    if not os.path.exists(MAVEN_INSTALL_DIR):
        return False, "java.service.maven_not_installed"

    remove_maven_env()

    try:
        shutil.rmtree(MAVEN_INSTALL_DIR)
        logger.info("Maven uninstalled successfully")
        return True, "java.service.maven_uninstall_success"
    except OSError as e:
        logger.error(f"Failed to remove Maven directory: {e}")
        return False, "java.service.maven_remove_failed"


def add_maven_to_path() -> tuple[bool, str]:
    maven_dir = _find_maven_bin_dir()
    if not maven_dir:
        return False, "java.service.maven_not_installed"
    bin_dir = os.path.join(maven_dir, "bin")
    return _add_to_path(bin_dir)


def remove_maven_env() -> tuple[bool, str]:
    maven_dir = _find_maven_bin_dir()
    if maven_dir:
        bin_dir = os.path.join(maven_dir, "bin")
        return _remove_from_path(bin_dir)

    maven_keywords = ["maven", "apache-maven"]
    removed = False
    for scope, reader, writer in [("hklm", _read_path_hklm, _write_path_hklm), ("hkcu", _read_path_hkcu, _write_path_hkcu)]:
        current = reader()
        if current is None:
            continue
        paths = [p.strip() for p in current.split(";") if p.strip()]
        cleaned = []
        changed = False
        for p in paths:
            p_lower = p.lower()
            should_remove = False
            for kw in maven_keywords:
                if kw in p_lower:
                    should_remove = True
                    break
            if should_remove:
                logger.info(f"Removing Maven-related path from {scope} PATH: {p}")
                changed = True
            else:
                cleaned.append(p)
        if changed:
            writer(";".join(cleaned))
            removed = True

    if removed:
        return True, "java.service.removed_from_path"
    return True, "java.service.not_in_path"


def is_maven_in_path() -> bool:
    maven_dir = _find_maven_bin_dir()
    if maven_dir:
        bin_dir = os.path.join(maven_dir, "bin")
        return _find_in_path(bin_dir)

    for reader in [_read_path_hklm, _read_path_hkcu]:
        current = reader()
        if current is None:
            continue
        for p in current.split(";"):
            p_lower = p.strip().lower()
            if "maven" in p_lower and "bin" in p_lower:
                return True
    return False
