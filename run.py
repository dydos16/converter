#!/usr/bin/env python3
"""
Запуск приложения с автоматической установкой всех зависимостей
"""
import sys
import os
import platform
import subprocess
import shutil
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


def run_command(cmd, description):
    """Выполняет команду и выводит прогресс"""
    print(f"\n📦 {description}...")
    print(f"   Команда: {' '.join(cmd)}")

    try:
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

        if process.returncode == 0:
            print(f"   ✅ {description} завершена")
            return True
        else:
            print(f"   ❌ Ошибка {description}")
            return False

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def install_pip():
    """Устанавливает pip если его нет"""
    os_name = get_os()

    if os_name == 'windows':
        return True  # На Windows pip обычно уже есть

    # Проверяем, есть ли pip
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

    # Проверяем, существует ли requirements.txt
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("\n⚠️  requirements.txt не найден!")
        return False

    # Формируем команду
    if os_name == 'windows':
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
    else:
        cmd = [sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-r', 'requirements.txt']

    return run_command(cmd, "Установка Python пакетов")


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


def check_libreoffice_installed():
    """Проверяет, установлен ли LibreOffice"""
    os_name = get_os()

    if os_name == 'macos':
        # Проверяем встроенный в проект
        app_path = Path(__file__).parent / "resources" / "libreoffice" / "macos" / "LibreOffice.app"
        if app_path.exists():
            return True
        # Проверяем системный
        if Path('/Applications/LibreOffice.app').exists():
            return True

    elif os_name == 'windows':
        # Проверяем системную установку
        if Path('C:/Program Files/LibreOffice/program/soffice.exe').exists() or \
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe').exists():
            return True
        # Проверяем встроенную в проект распакованную версию
        extracted_path = Path(
            __file__).parent / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        if extracted_path.exists():
            return True
        return False

    else:  # linux
        # Проверяем системный
        if shutil.which('libreoffice') or shutil.which('soffice'):
            return True
        # Проверяем встроенный
        linux_dir = Path(__file__).parent / "resources" / "libreoffice" / "linux"
        if linux_dir.exists():
            return True

    return False


def install_libreoffice():
    """Устанавливает LibreOffice через скрипт"""
    print("\n" + "=" * 60)
    print("  Установка LibreOffice...")
    print("=" * 60)

    # Проверяем, есть ли скрипт
    script_path = Path(__file__).parent / "download_libreoffice.py"
    if not script_path.exists():
        print("❌ Скрипт download_libreoffice.py не найден")
        return False

    try:
        # Импортируем и запускаем скрипт установки
        sys.path.insert(0, str(Path(__file__).parent))
        from download_libreoffice import main as download_main
        success = download_main()

        if success:
            print("\n✅ LibreOffice успешно установлен!")
            return True
        else:
            print("\n❌ Не удалось установить LibreOffice")
            return False

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при установке: {e}")
        return False


def main():
    """Основная функция"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка и запуск")
    print("=" * 60)

    os_name = get_os()
    print(f"\n🖥️  Операционная система: {os_name}")
    print(f"🐍 Python: {sys.executable}")

    # 1. Устанавливаем pip если нужно
    install_pip()

    # 2. Устанавливаем Python пакеты из requirements.txt
    print("\n" + "-" * 60)
    if not install_requirements():
        print("\n⚠️  Не удалось установить пакеты автоматически")
        print("Попробуйте установить вручную:")
        if os_name == 'windows':
            print("  pip install -r requirements.txt")
        else:
            print("  pip3 install --break-system-packages -r requirements.txt")

        response = input("\nПродолжить без установки? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)

    # 3. Проверяем установку Python пакетов
    missing = check_python_packages()
    if missing:
        print(f"\n⚠️  Всё ещё отсутствуют: {', '.join(missing)}")
        print("Попробуйте установить вручную:")
        if os_name == 'windows':
            print("  pip install -r requirements.txt")
        else:
            print("  pip3 install --break-system-packages -r requirements.txt")

        response = input("\nПродолжить без установки? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    else:
        print("\n✅ Все Python пакеты установлены")

    # 4. Проверяем и устанавливаем LibreOffice
    print("\n" + "-" * 60)
    if not check_libreoffice_installed():
        print("\n⚠️  LibreOffice не найден!")

        if not install_libreoffice():
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
        print("\n✅ LibreOffice найден")

    # 5. Запускаем основное приложение
    print("\n" + "=" * 60)
    print("  Запуск приложения...")
    print("=" * 60 + "\n")

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