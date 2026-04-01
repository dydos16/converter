#!/usr/bin/env python3
"""
Запуск приложения с автоматической установкой всех зависимостей
"""
import sys
import os
import platform
import subprocess
import shutil
import importlib.util
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))


def get_os():
    """Определяет операционную систему"""
    system = platform.system().lower()
    if system == 'darwin':
        return 'macos'
    elif system == 'windows':
        return 'windows'
    else:
        return 'linux'


def get_arch():
    """Определяет архитектуру процессора"""
    machine = platform.machine().lower()
    if machine in ['arm64', 'aarch64']:
        return 'arm64'
    else:
        return 'x86_64'


def run_command(cmd, description, show_output=True):
    """Выполняет команду и выводит прогресс"""
    print(f"\n📦 {description}...")
    print(f"   Команда: {' '.join(cmd)}")

    try:
        if show_output:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in process.stdout:
                if 'Downloading' in line or 'Collecting' in line:
                    print(f"   {line.strip()}")
                elif 'Successfully installed' in line:
                    print(f"   ✅ {line.strip()}")

            process.wait()
            return process.returncode == 0
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def install_pip():
    """Устанавливает pip если его нет"""
    os_name = get_os()

    if os_name == 'windows':
        return True

    if shutil.which('pip') or shutil.which('pip3'):
        return True

    print("\n📦 Установка pip...")
    try:
        subprocess.run([sys.executable, '-m', 'ensurepip', '--upgrade'], check=True)
        return True
    except:
        return False


def install_requirements():
    """Устанавливает зависимости из requirements.txt"""
    os_name = get_os()

    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("\n⚠️  requirements.txt не найден!")
        return False

    if os_name == 'windows':
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
    else:
        cmd = [sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-r', 'requirements.txt']

    return run_command(cmd, "Установка Python пакетов")


def check_python_packages():
    """Проверяет наличие всех необходимых Python пакетов"""
    required = [
        'loguru', 'PySide6', 'docx', 'pptx', 'reportlab',
        'PIL', 'openpyxl', 'requests', 'colorama', 'lxml',
        'pdf2docx', 'pdfplumber', 'fitz', 'pdf2image', 'pypdf'
    ]

    missing = []
    for package in required:
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'docx':
                __import__('docx')
            elif package == 'pptx':
                __import__('pptx')
            elif package == 'fitz':
                __import__('fitz')
            else:
                __import__(package)
        except ImportError:
            missing.append(package)

    return missing


def check_poppler_installed():
    """Проверяет наличие poppler для pdf2image"""
    os_name = get_os()

    if os_name == 'windows':
        # Проверяем наличие pdftoppm.exe
        poppler_paths = [
            Path('C:/Program Files/poppler/bin/pdftoppm.exe'),
            Path('C:/Program Files (x86)/poppler/bin/pdftoppm.exe'),
        ]
        for path in poppler_paths:
            if path.exists():
                return True
        return False
    elif os_name == 'macos':
        # На macOS poppler можно установить через brew
        return shutil.which('pdftoppm') is not None
    else:  # linux
        return shutil.which('pdftoppm') is not None


def install_poppler():
    """Устанавливает poppler для pdf2image"""
    os_name = get_os()

    print("\n📦 Установка poppler...")

    if os_name == 'windows':
        print("""
Для Windows необходимо установить poppler вручную:
1. Скачайте poppler с https://github.com/oschwartz10612/poppler-windows/releases/
2. Распакуйте в C:/Program Files/poppler
3. Добавьте C:/Program Files/poppler/bin в PATH
        """)
        return False
    elif os_name == 'macos':
        if shutil.which('brew'):
            result = subprocess.run(['brew', 'install', 'poppler'], capture_output=True)
            return result.returncode == 0
        else:
            print("Установите Homebrew: https://brew.sh")
            return False
    else:  # linux
        try:
            subprocess.run(['sudo', 'apt-get', 'update'], capture_output=True)
            result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'poppler-utils'], capture_output=True)
            return result.returncode == 0
        except:
            return False


def check_libreoffice_installed():
    """Проверяет, установлен ли LibreOffice и работает ли"""
    project_root = Path(__file__).parent
    os_name = get_os()

    # Проверяем системную установку
    if os_name == 'windows':
        if Path('C:/Program Files/LibreOffice/program/soffice.exe').exists() or \
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe').exists():
            return True
    elif os_name == 'macos':
        if Path('/Applications/LibreOffice.app').exists():
            return True
    else:  # linux
        if shutil.which('libreoffice') or shutil.which('soffice'):
            return True

    # Проверяем встроенную в проект версию
    if os_name == 'windows':
        extracted = project_root / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        if extracted.exists():
            return True
        msi_files = list((project_root / "resources" / "libreoffice" / "windows").glob("*.msi"))
        if msi_files:
            return True
    elif os_name == 'macos':
        app_path = project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app"
        if app_path.exists():
            soffice = app_path / "Contents" / "MacOS" / "soffice"
            if soffice.exists():
                try:
                    result = subprocess.run([str(soffice), '--version'],
                                            capture_output=True, timeout=5)
                    return result.returncode == 0
                except:
                    pass
    else:  # linux
        linux_dir = project_root / "resources" / "libreoffice" / "linux"
        if linux_dir.exists():
            return True

    return False


def install_libreoffice():
    """Устанавливает LibreOffice"""
    script_path = Path(__file__).parent / "download_libreoffice.py"

    if not script_path.exists():
        print("❌ Скрипт download_libreoffice.py не найден")
        return False

    try:
        spec = importlib.util.spec_from_file_location("download_libreoffice", script_path)
        download_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(download_module)

        success = download_module.main()
        return success
    except Exception as e:
        print(f"❌ Ошибка при установке LibreOffice: {e}")
        return False


def show_manual_instructions():
    """Показывает инструкции для ручной установки"""
    os_name = get_os()

    print("\n" + "=" * 60)
    print("  Инструкция по ручной установке")
    print("=" * 60)

    if os_name == 'windows':
        print("""
📥 Установите необходимые компоненты:

1. LibreOffice (для документов и презентаций):
   https://www.libreoffice.org/download/download-libreoffice/

2. poppler (для PDF в изображения):
   https://github.com/oschwartz10612/poppler-windows/releases/
   Распакуйте в C:/Program Files/poppler
   Добавьте C:/Program Files/poppler/bin в PATH

3. Python пакеты:
   pip install -r requirements.txt
""")
    elif os_name == 'macos':
        print("""
📥 Установите необходимые компоненты:

1. LibreOffice:
   brew install --cask libreoffice

2. poppler:
   brew install poppler

3. Python пакеты:
   pip3 install --break-system-packages -r requirements.txt
""")
    else:
        print("""
📥 Установите необходимые компоненты:

Ubuntu/Debian:
   sudo apt update
   sudo apt install -y libreoffice poppler-utils
   pip3 install --break-system-packages -r requirements.txt

Fedora/RHEL:
   sudo dnf install libreoffice poppler-utils
   pip3 install --break-system-packages -r requirements.txt
""")


def main():
    """Основная функция"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка и запуск")
    print("=" * 60)

    os_name = get_os()
    arch = get_arch()
    print(f"\n🖥️  Операционная система: {os_name}")
    print(f"📐 Архитектура: {arch}")
    print(f"🐍 Python: {sys.executable}")

    # 1. Устанавливаем pip если нужно
    install_pip()

    # 2. Устанавливаем Python пакеты из requirements.txt
    print("\n" + "-" * 60)
    if not install_requirements():
        print("\n⚠️  Не удалось установить пакеты автоматически")
        response = input("\nПродолжить без установки? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)

    # 3. Проверяем установку Python пакетов
    missing = check_python_packages()
    if missing:
        print(f"\n⚠️  Всё ещё отсутствуют: {', '.join(missing)}")
        response = input("\nПродолжить без установки? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    else:
        print("\n✅ Все Python пакеты установлены")

    # 4. Проверяем poppler для PDF в изображения
    print("\n" + "-" * 60)
    if not check_poppler_installed():
        print("\n⚠️  poppler не найден! (нужен для конвертации PDF в изображения)")
        response = input("\nУстановить poppler автоматически? (y/n): ").lower()
        if response == 'y':
            if not install_poppler():
                print("\n⚠️  Не удалось установить poppler автоматически")
                show_manual_instructions()
        else:
            print("\nПродолжаем без poppler (конвертация PDF в изображения будет недоступна)")
    else:
        print("\n✅ poppler найден")

    # 5. Проверяем и устанавливаем LibreOffice
    print("\n" + "-" * 60)
    if not check_libreoffice_installed():
        print("\n⚠️  LibreOffice не найден!")

        response = input("\nУстановить LibreOffice автоматически? (y/n): ").lower()
        if response == 'y':
            if not install_libreoffice():
                print("\n❌ Не удалось установить LibreOffice автоматически")
                show_manual_instructions()
                response = input("\nПродолжить без LibreOffice? (y/n): ").lower()
                if response != 'y':
                    sys.exit(1)
            else:
                print("\n✅ LibreOffice успешно установлен!")
        else:
            print("\nПродолжаем без LibreOffice (конвертация документов будет недоступна)")
    else:
        print("\n✅ LibreOffice найден и работает")

    # 6. Запускаем основное приложение
    print("\n" + "=" * 60)
    print("  Запуск приложения...")
    print("=" * 60 + "\n")

    try:
        from src.main import main as app_main
        app_main()
    except ImportError as e:
        print(f"\n❌ Ошибка импорта: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()