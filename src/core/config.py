import os
import sys

APP_VERSION = "1.0.0"
WEBSITE_URL = "https://www.wwwoop.com"

WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 480
WINDOW_DEFAULT_WIDTH = 960
WINDOW_DEFAULT_HEIGHT = 640

TOPBAR_HEIGHT = 32
FOOTER_HEIGHT = 32

NAV_ITEMS = [
    ("home", "Home"),
    ("mysql", "MySQL"),
    ("redis", "Redis"),
    ("java", "Java"),
    ("php", "PHP"),
    ("python", "Python"),
    ("node", "Node"),
]

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    RESOURCE_DIR = APP_DIR

BASE_DIR = APP_DIR
ASSETS_DIR = os.path.join(RESOURCE_DIR, "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
STYLES_DIR = os.path.join(ASSETS_DIR, "styles")
INSTALLATION_PKG_DIR = os.path.join(APP_DIR, "installation-package")
WORKSPACE_DIR = os.path.join(APP_DIR, "workspace")

# MySQL specific paths
MYSQL_PKG_DIR = os.path.join(INSTALLATION_PKG_DIR, "mysql")
MYSQL_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "mysql")

PHP_PKG_DIR = os.path.join(INSTALLATION_PKG_DIR, "php", "datas")
PHP_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "php")
PHP_EXPAND_DIR = os.path.join(INSTALLATION_PKG_DIR, "php", "expand")
COMPOSER_PKG_PATH = os.path.join(PHP_EXPAND_DIR, "composer.zip")
COMPOSER_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "composer")

REDIS_PKG_DIR = os.path.join(INSTALLATION_PKG_DIR, "redis")
REDIS_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "redis")

JAVA_PKG_DIR = os.path.join(INSTALLATION_PKG_DIR, "java", "jdk")
JAVA_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "java")

MAVEN_PKG_PATH = os.path.join(INSTALLATION_PKG_DIR, "java", "maven", "apache-maven-3.9.15-bin.zip")
MAVEN_SETTINGS_TEMPLATE = os.path.join(INSTALLATION_PKG_DIR, "java", "maven", "settings.xml.example")
MAVEN_INSTALL_DIR = os.path.join(WORKSPACE_DIR, "maven")
