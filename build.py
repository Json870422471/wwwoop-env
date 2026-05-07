import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(PROJECT_DIR, "main.py")
APP_NAME = "wwwoop-env"
ICON_PATH = os.path.join(PROJECT_DIR, "assets", "icons", "app.ico")

BUILD_CMD = (
    f'pyinstaller --noconfirm --onedir --windowed '
    f'--name "{APP_NAME}" '
    f'--add-data "assets;assets" '
)

if os.path.exists(ICON_PATH):
    BUILD_CMD += f'--icon "{ICON_PATH}" '

BUILD_CMD += f'"{MAIN_SCRIPT}"'


def main():
    print(f"开始打包: {APP_NAME}")
    print(f"命令: {BUILD_CMD}")
    os.system(BUILD_CMD)
    print("打包完成！输出目录: dist/")


if __name__ == "__main__":
    main()
