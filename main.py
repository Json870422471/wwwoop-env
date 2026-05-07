import sys
import os
import ctypes


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    try:
        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = ""
        else:
            executable = sys.executable
            params = f'"{os.path.abspath(__file__)}"'

        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
    except Exception as e:
        print(f"Failed to elevate: {e}")


if __name__ == "__main__":
    if not is_admin():
        run_as_admin()
        sys.exit(0)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from src.app import run

    run()
