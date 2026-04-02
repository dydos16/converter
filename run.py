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

# Флаг для определения, что мы в собранном приложении
IS_FROZEN = getattr(sys, 'frozen', False)


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


def get_user_input(prompt, default='y'):
    """Получает ввод пользователя или возвращает значение по умолчанию в собранном приложении"""
    if IS_FROZEN:
        print(f"{prompt} (автоматически: {default})")
        return default
    else:
        return input(prompt).lower()


def install_requirements():
    """Устанавливает зависимости из requirements.txt с правильными флагами"""
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("\n⚠️  requirements.txt не найден!")
        return False

    os_name = get_os()

    # Базовые флаги для pip
    pip_flags = []

    # Для macOS и Linux добавляем флаг для обхода PEP 668
    if os_name in ['macos', 'linux']:
        pip_flags.append('--break-system-packages')

    # Устанавливаем зависимости
    cmd = [sys.executable, '-m', 'pip', 'install'] + pip_flags + ['-r', 'requirements.txt']

    return run_command(cmd, "Установка Python пакетов")


def check_python_packages():
    """Проверяет наличие всех необходимых Python пакетов"""
    required = [
        'PySide6', 'loguru', 'PIL', 'fitz', 'docx', 'pptx',
        'openpyxl', 'pdfplumber', 'camelot', 'tabula', 'pandas'
    ]

    # Опциональные пакеты
    optional = ['pdf2image', 'pdf2docx', 'pypdf']

    missing = []
    optional_missing = []

    for package in required:
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'fitz':
                __import__('fitz')
            elif package == 'docx':
                __import__('docx')
            elif package == 'pptx':
                __import__('pptx')
            elif package == 'camelot':
                __import__('camelot')
            elif package == 'tabula':
                __import__('tabula')
            else:
                __import__(package)
        except ImportError:
            missing.append(package)

    for package in optional:
        try:
            __import__(package)
        except ImportError:
            optional_missing.append(package)

    return missing, optional_missing


def check_libreoffice_installed():
    """Проверяет, установлен ли LibreOffice и работает ли"""
    import shutil
    import platform

    system = platform.system().lower()

    # Проверяем системную установку
    if system == 'windows':
        if Path('C:/Program Files/LibreOffice/program/soffice.exe').exists() or \
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe').exists():
            return True
    elif system == 'darwin':
        if Path('/Applications/LibreOffice.app').exists():
            return True
    else:  # linux
        if shutil.which('libreoffice') or shutil.which('soffice'):
            return True

    # Проверяем встроенную в проект версию
    project_root = Path(__file__).parent

    if system == 'darwin':
        app_path = project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app"
        if app_path.exists():
            return True

    return False


def install_libreoffice():
    """Устанавливает LibreOffice через скрипт"""
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


def install_poppler():
    """Устанавливает poppler для pdf2image"""
    os_name = get_os()

    print("\n📦 Установка poppler...")

    if os_name == 'darwin':
        if shutil.which('brew'):
            result = subprocess.run(['brew', 'install', 'poppler'], capture_output=True)
            if result.returncode == 0:
                print("✅ poppler установлен через Homebrew")
                return True
            else:
                print("❌ Не удалось установить poppler через Homebrew")
                return False
        else:
            print("⚠️  Homebrew не найден. Установите poppler вручную:")
            print("   brew install poppler")
            return False

    elif os_name == 'linux':
        try:
            subprocess.run(['sudo', 'apt-get', 'update'], capture_output=True)
            result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'poppler-utils'], capture_output=True)
            if result.returncode == 0:
                print("✅ poppler установлен через apt")
                return True
        except:
            pass
        return False

    else:  # windows
        print("⚠️  Для Windows установите poppler вручную:")
        print("   1. Скачайте с https://github.com/oschwartz10612/poppler-windows/releases/")
        print("   2. Распакуйте в C:/Program Files/poppler")
        print("   3. Добавьте C:/Program Files/poppler/bin в PATH")
        return False


def show_manual_instructions(missing_packages):
    """Показывает инструкции для ручной установки"""
    os_name = get_os()

    print("\n" + "=" * 60)
    print("  Инструкция по ручной установке")
    print("=" * 60)

    if missing_packages:
        print(f"\n📦 Отсутствуют пакеты: {', '.join(missing_packages)}")

    print("\nУстановите недостающие пакеты:")

    if os_name in ['macos', 'linux']:
        print(f"  pip3 install --break-system-packages {' '.join(missing_packages)}")
    else:
        print(f"  pip install {' '.join(missing_packages)}")

    print("\nИли установите все сразу:")
    if os_name in ['macos', 'linux']:
        print("  pip3 install --break-system-packages -r requirements.txt")
    else:
        print("  pip install -r requirements.txt")


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

    # 1. Устанавливаем Python пакеты из requirements.txt
    print("\n" + "-" * 60)
    if not install_requirements():
        print("\n⚠️  Не удалось установить пакеты автоматически")
        missing, optional = check_python_packages()
        if missing:
            show_manual_instructions(missing)
            response = get_user_input("\nПродолжить без установки? (y/n): ", 'y')
            if response != 'y':
                sys.exit(1)
    else:
        print("\n✅ Все основные пакеты установлены")

    # 2. Проверяем установку Python пакетов
    missing, optional = check_python_packages()
    if missing:
        print(f"\n⚠️  Отсутствуют обязательные пакеты: {', '.join(missing)}")
        show_manual_instructions(missing)
        response = get_user_input("\nПродолжить без этих пакетов? (y/n): ", 'y')
        if response != 'y':
            sys.exit(1)

    if optional:
        print(f"\nℹ️  Опциональные пакеты (не обязательны): {', '.join(optional)}")
        print("   Некоторые функции могут быть недоступны")

    # 3. Проверяем poppler для PDF в изображения
    print("\n" + "-" * 60)
    try:
        from pdf2image import convert_from_path
        print("✅ pdf2image готов к работе")
    except ImportError:
        print("⚠️  pdf2image не установлен (конвертация PDF в изображения будет недоступна)")

    # 4. Проверяем и устанавливаем LibreOffice
    print("\n" + "-" * 60)
    if not check_libreoffice_installed():
        print("\n⚠️  LibreOffice не найден!")

        response = get_user_input("\nУстановить LibreOffice автоматически? (y/n): ", 'y')
        if response == 'y':
            if not install_libreoffice():
                print("\n❌ Не удалось установить LibreOffice автоматически")
                print("\nУстановите LibreOffice вручную:")
                if os_name == 'darwin':
                    print("  brew install --cask libreoffice")
                elif os_name == 'windows':
                    print("  https://www.libreoffice.org/download/")
                else:
                    print("  sudo apt install libreoffice")

                response2 = get_user_input("\nПродолжить без LibreOffice? (y/n): ", 'y')
                if response2 != 'y':
                    sys.exit(1)
            else:
                print("\n✅ LibreOffice успешно установлен!")
        else:
            print("\nПродолжаем без LibreOffice (конвертация документов будет недоступна)")
    else:
        print("\n✅ LibreOffice найден")

    # 5. Запускаем основное приложение
    print("\n" + "=" * 60)
    print("  Запуск приложения...")
    print("=" * 60 + "\n")

    try:
        from src.main import main as app_main
        app_main()
    except ImportError as e:
        print(f"\n❌ Ошибка импорта: {e}")
        print("\nПроверьте структуру проекта. Должна быть папка src с файлом main.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()