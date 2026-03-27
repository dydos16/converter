#!/usr/bin/env python3
"""
Запуск приложения с автоматической установкой зависимостей
"""
import sys
import subprocess
import platform
import os
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


def find_pip():
    """Находит pip на Windows даже если не в PATH"""
    os_name = get_os()

    if os_name == 'windows':
        # Ищем pip в стандартных местах
        possible_paths = [
            Path(sys.executable).parent / 'pip.exe',
            Path(sys.executable).parent / 'Scripts' / 'pip.exe',
            Path(os.environ.get('APPDATA', '')) / 'Python' / 'Scripts' / 'pip.exe',
            Path('C:/Python*/Scripts/pip.exe'),
            Path('C:/Program Files/Python*/Scripts/pip.exe'),
            Path('C:/Users/*/AppData/Local/Programs/Python/Python*/Scripts/pip.exe'),
        ]

        # Ищем по маске
        for pattern in ['C:/Python*/Scripts/pip.exe', 'C:/Program Files/Python*/Scripts/pip.exe']:
            from glob import glob
            for path in glob(pattern):
                if Path(path).exists():
                    return path

        for path in possible_paths:
            if path.exists():
                return str(path)

        # Если не нашли, используем python -m pip
        return None

    elif os_name == 'macos':
        return 'pip3'
    else:
        return 'pip3'


def get_pip_command():
    """Возвращает команду pip для текущей ОС"""
    os_name = get_os()
    pip_cmd = find_pip()

    if os_name == 'windows':
        if pip_cmd:
            return [pip_cmd, 'install', '-r', 'requirements.txt']
        else:
            # Используем python -m pip
            return [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
    else:
        return ['pip3', 'install', '--break-system-packages', '-r', 'requirements.txt']


def install_requirements():
    """Устанавливает зависимости из requirements.txt"""
    os_name = get_os()
    cmd = get_pip_command()

    print(f"\n📦 Установка зависимостей для {os_name}...")
    print(f"Команда: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=(os_name == 'windows'))

        if result.returncode == 0:
            print("✅ Зависимости успешно установлены!")
            return True
        else:
            print("❌ Ошибка установки зависимостей:")
            if result.stderr:
                print(result.stderr)
            if result.stdout:
                print(result.stdout)
            return False

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def check_and_install():
    """Проверяет наличие модулей и устанавливает при необходимости"""
    try:
        import loguru
        import PySide6
        import docx
        import pptx
        import reportlab
        import PIL
        import openpyxl
        import requests
        import colorama
        import lxml
        print("✅ Все модули уже установлены")
        return True
    except ImportError as e:
        print(f"⚠️  Отсутствует модуль: {e.name}")
        print("🔄 Автоматическая установка...")
        return install_requirements()


def check_libreoffice():
    """Проверяет наличие LibreOffice"""
    os_name = get_os()

    if os_name == 'windows':
        paths = [
            'C:/Program Files/LibreOffice/program/soffice.exe',
            'C:/Program Files (x86)/LibreOffice/program/soffice.exe',
            str(Path.home() / '.file-converter' / 'LibreOffice' / 'program' / 'soffice.exe'),
        ]
        for path in paths:
            if Path(path).exists():
                return True
        return False
    elif os_name == 'macos':
        if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
            return True
        if Path(Path.home() / '.file-converter' / 'LibreOffice' / 'Contents' / 'MacOS' / 'soffice').exists():
            return True
        return False
    else:
        import shutil
        return shutil.which('libreoffice') is not None or shutil.which('soffice') is not None


def main():
    """Запуск с проверкой зависимостей"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Проверка зависимостей")
    print("=" * 60 + "\n")

    os_name = get_os()
    print(f"🖥️  Операционная система: {os_name}")
    print(f"🐍 Python: {sys.executable}")

    # Проверяем и устанавливаем Python зависимости
    if not check_and_install():
        print("\n❌ Ошибка при установке Python зависимостей!")
        print("\nПопробуйте установить вручную:")
        if os_name == 'windows':
            print("  python -m pip install -r requirements.txt")
        else:
            print("  pip3 install --break-system-packages -r requirements.txt")
        sys.exit(1)

    # Проверяем LibreOffice
    if not check_libreoffice():
        print("\n⚠️  LibreOffice не найден!")
        print("📄 LibreOffice нужен для конвертации Word и PowerPoint файлов.")
        print("\nУстановите LibreOffice:")
        if os_name == 'macos':
            print("  brew install --cask libreoffice")
        elif os_name == 'windows':
            print("  Скачайте с https://www.libreoffice.org/download/")
        else:
            print("  sudo apt install libreoffice")
        print("\nИли продолжайте без LibreOffice (конвертация будет ограничена).")

        response = input("\nПродолжить без LibreOffice? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)

    print("\n🚀 Запуск приложения...\n")

    # Запускаем основное приложение
    try:
        from src.main import main
        main()
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()