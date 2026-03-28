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
        ]

        # Поиск по маске
        from glob import glob
        for pattern in ['C:/Python*/Scripts/pip.exe', 'C:/Program Files/Python*/Scripts/pip.exe']:
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


def check_python_packages():
    """Проверяет наличие всех необходимых Python пакетов"""
    required = [
        'loguru', 'PySide6', 'docx', 'pptx', 'reportlab',
        'PIL', 'openpyxl', 'requests', 'colorama', 'lxml'
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
            else:
                __import__(package)
        except ImportError:
            missing.append(package)

    return missing


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


def install_libreoffice_auto():
    """Автоматическая установка LibreOffice"""
    print("\n🔄 Автоматическая установка LibreOffice...")

    try:
        from src.core.libreoffice_manager import LibreOfficeManager

        manager = LibreOfficeManager()

        def progress_callback(progress):
            print(f"\r📥 Скачивание и установка: {progress}%", end='', flush=True)

        if manager.install(progress_callback):
            print("\n✅ LibreOffice успешно установлен!")
            return True
        else:
            print("\n❌ Не удалось установить LibreOffice автоматически")
            return False

    except Exception as e:
        print(f"\n❌ Ошибка при установке LibreOffice: {e}")
        return False


def main():
    """Запуск с проверкой зависимостей"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Проверка зависимостей")
    print("=" * 60 + "\n")

    os_name = get_os()
    print(f"🖥️  Операционная система: {os_name}")
    print(f"🐍 Python: {sys.executable}")

    # Проверяем Python зависимости
    missing = check_python_packages()

    if missing:
        print(f"\n⚠️  Отсутствуют Python пакеты: {', '.join(missing)}")
        print("🔄 Автоматическая установка...")

        if not install_requirements():
            print("\n❌ Ошибка при установке Python зависимостей!")
            print("\nПопробуйте установить вручную:")
            if os_name == 'windows':
                print("  python -m pip install -r requirements.txt")
            else:
                print("  pip3 install --break-system-packages -r requirements.txt")
            sys.exit(1)

        # Проверяем ещё раз
        missing = check_python_packages()
        if missing:
            print(f"\n❌ После установки всё ещё отсутствуют: {missing}")
            sys.exit(1)
    else:
        print("✅ Все Python пакеты установлены")

    # Проверяем LibreOffice
    if not check_libreoffice():
        print("\n⚠️  LibreOffice не найден!")

        # Пробуем установить автоматически
        if install_libreoffice_auto():
            # Проверяем после установки
            if not check_libreoffice():
                print("\n❌ LibreOffice не установился автоматически")
                print("\nУстановите вручную:")
                if os_name == 'macos':
                    print("  brew install --cask libreoffice")
                elif os_name == 'windows':
                    print("  скачайте с https://www.libreoffice.org/download/")
                else:
                    print("  sudo apt install libreoffice")

                response = input("\nПродолжить без LibreOffice? (y/n): ").lower()
                if response != 'y':
                    sys.exit(1)
            else:
                print("✅ LibreOffice успешно установлен!")
        else:
            print("\n❌ Не удалось установить LibreOffice автоматически")
            print("\nУстановите вручную:")
            if os_name == 'macos':
                print("  brew install --cask libreoffice")
            elif os_name == 'windows':
                print("  скачайте с https://www.libreoffice.org/download/")
            else:
                print("  sudo apt install libreoffice")

            response = input("\nПродолжить без LibreOffice? (y/n): ").lower()
            if response != 'y':
                sys.exit(1)
    else:
        print("✅ LibreOffice найден")

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