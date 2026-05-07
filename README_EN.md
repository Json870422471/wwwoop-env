# Development Environment Setup Tool

> A one-stop development environment integration tool — say goodbye to tedious configuration and focus on coding!
>
> 🌐 More IT learning resources at [www.wwwoop.com](https://www.wwwoop.com) (The Bookstore for IT Professionals)

## Introduction

**Development Environment Setup Tool** is a Windows 10/11 integration tool provided by the WWWOOP platform. With this tool, you can install various development environments and tools with one click, eliminating the hassle of manual environment configuration.

## Project Directory Structure

```
wwwoop-env/
├── main.py                          # Entry point (auto-elevates to admin)
├── requirements.txt                 # Dependencies
├── build.py                         # PyInstaller build script
├── assets/                          # Resource files
│   └── icons/                       # Icons
│       └── app.ico                  # Application icon
├── installation-package/            # Bundled installation packages
│   ├── java/                        # Java environment
│   │   ├── jdk/                     # JDK packages
│   │   └── maven/                   # Maven package & config template
│   │       ├── apache-maven-3.9.15-bin.zip
│   │       └── settings.xml.example
│   ├── mysql/                       # MySQL environment
│   │   ├── mysql-5.7.26-winx64.zip
│   │   ├── mysql-8.0.46-winx64.zip
│   │   └── my.ini.example           # MySQL config template
│   ├── php/                         # PHP environment
│   │   ├── datas/                   # PHP packages
│   │   │   ├── php-7.4.33-nts-Win32-vc15-x64.zip
│   │   │   └── php-8.5.5-nts-Win32-vs17-x64.zip
│   │   └── expand/                  # PHP extensions
│   │       └── composer.zip
│   └── redis/                       # Redis environment
│       └── Redis-8.6.2-Windows-x64-msys2-with-Service.zip
├── logs/                            # Runtime logs (auto-generated)
└── src/                             # Source code
    ├── app.py                       # QApplication init & launch
    ├── core/
    │   ├── config.py                # Global constants, colors, paths
    │   └── i18n.py                  # Internationalization (ZH/EN)
    ├── services/                    # Business logic layer
    │   ├── mysql_service.py         # MySQL install/uninstall/start/stop/config
    │   ├── redis_service.py         # Redis install/uninstall/start/stop/config
    │   ├── java_service.py          # Java/Maven install & config
    │   └── php_service.py           # PHP/Composer install & config
    ├── ui/
    │   ├── main_window.py           # Main window (top nav bar + page stack)
    │   ├── pages/                   # Feature pages
    │   │   ├── home_page.py         # Home page
    │   │   ├── mysql_page.py        # MySQL management page
    │   │   ├── redis_page.py        # Redis management page
    │   │   ├── java_page.py         # Java management page
    │   │   ├── php_page.py          # PHP management page
    │   │   ├── python_page.py       # Python management page
    │   │   └── node_page.py         # Node management page
    │   └── components/              # Reusable UI components
    │       ├── topbar.py            # Top navigation bar
    │       └── footer.py            # Footer status bar
    └── utils/
        └── logger.py                # Logging utility
```

## Bundled Installation Packages

The `installation-package/` directory contains bundled installation packages for each environment. The application reads packages from this directory at runtime. Currently includes:

| Environment | Package | Description |
|-------------|---------|-------------|
| MySQL | mysql-5.7.26-winx64.zip | MySQL 5.7 portable (no installer) |
| MySQL | mysql-8.0.46-winx64.zip | MySQL 8.0 portable (no installer) |
| Redis | Redis-8.6.2-Windows-x64-msys2-with-Service.zip | Redis 8.6.2 with service installation |
| Java | jdk/ | JDK packages (add manually) |
| Maven | apache-maven-3.9.15-bin.zip | Maven 3.9.15 |
| PHP | php-7.4.33-nts-Win32-vc15-x64.zip | PHP 7.4 NTS x64 |
| PHP | php-8.5.5-nts-Win32-vs17-x64.zip | PHP 8.5 NTS x64 |
| Composer | composer.zip | PHP package manager |

> **Note**: Due to large file sizes, the packages in `installation-package/` are not committed to the repository. Please download the corresponding release from the project's **Releases** page to get the full bundled packages.

> **Note**: If the bundled packages don't meet your needs, you can download the portable version (ZIP format) of your desired version and place it in the corresponding subdirectory under `installation-package/`.

## Requirements

- **OS**: Windows 10 / 11
- **Python**: 3.12 (conda environment: `oop-env`)
- **Package Manager**: conda / pip

## Install Dependencies

### 1. Create and activate conda environment

```bash
conda create -n oop-env python=3.12
conda activate oop-env
```

### 2. Install project dependencies

```bash
pip install -r requirements.txt
```

Dependencies (`requirements.txt`):

| Package | Purpose |
|---------|---------|
| PyQt6>=6.6.0 | GUI framework |
| PyInstaller>=6.3.0 | Build to exe executable |

## Run the Project

```bash
conda activate oop-env
python main.py
```

After launch, you will see the main window with a top navigation bar and a page content area below.

## Build to exe

### One-click Build

```bash
python build.py
```

The built executable will be output to the `dist/wwwoop-env/` directory.

> **Important**: After building, you must manually copy the `installation-package/` folder from the project root into the `dist/wwwoop-env/` directory. Otherwise, the application will not be able to find the bundled installation packages at runtime, and the environment installation feature will not work.
>
> The directory structure after copying should look like:
> ```
> dist/wwwoop-env/
> ├── wwwoop-env.exe
> ├── assets/
> ├── installation-package/    ← Copy here manually
> │   ├── java/
> │   ├── mysql/
> │   ├── php/
> │   └── redis/
> └── ...
> ```

### Manual Build

```bash
pyinstaller --noconfirm --onedir --windowed --name "wwwoop-env" --add-data "assets;assets" main.py
```

To use a custom icon, place an `.ico` file in `assets/icons/` and name it `app.ico`. The build script will detect it automatically.

## Screenshots

### Home

![Home](dosc/首页.png)

### MySQL

![MySQL](dosc/mysql.png)

### Redis

![Redis](dosc/redis.png)

### Java

![Java](dosc/java.png)

### PHP

![PHP](dosc/php.png)

### Python

![Python](dosc/pythn.png)

### Node

![Node](dosc/node.png)

## Disclaimer

This software is an open-source project. Anyone is free to download, modify, and distribute it. Please use it at your own discretion. If you encounter any issues or have suggestions, feel free to contact the author.

The development environments provided by this software are intended for learning and development purposes only, and are not recommended for production use. The author assumes no responsibility for any consequences arising from the use of this software.

## Tech Stack

- **GUI Framework**: PyQt6
- **Language**: Python 3.12
- **Build Tool**: PyInstaller
- **Logging**: Python standard library logging

## Links

- Website: [www.wwwoop.com](https://www.wwwoop.com)
