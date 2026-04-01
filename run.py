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
        # Проверяем распакованную версию
        extracted = project_root / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        if extracted.exists():
            return True

        # Проверяем MSI файл
        msi_files = list((project_root / "resources" / "libreoffice" / "windows").glob("*.msi"))
        if msi_files:
            return True

        # Проверяем любую версию в resources
        for root, dirs, files in os.walk(project_root / "resources"):
            if 'soffice.exe' in files:
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


def install_libreoffice_via_script():
    """Устанавливает LibreOffice через скрипт download_libreoffice.py"""
    script_path = Path(__file__).parent / "download_libreoffice.py"

    if not script_path.exists():
        print("❌ Скрипт download_libreoffice.py не найден")
        return False

    try:
        # Используем importlib для импорта и запуска
        spec = importlib.util.spec_from_file_location("download_libreoffice", script_path)
        download_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(download_module)

        # Запускаем main из скрипта
        success = download_module.main()
        return success

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при установке: {e}")
        import traceback
        traceback.print_exc()
        return False


def install_libreoffice_via_subprocess():
    """Устанавливает LibreOffice через subprocess (альтернативный способ)"""
    script_path = Path(__file__).parent / "download_libreoffice.py"

    if not script_path.exists():
        print("❌ Скрипт download_libreoffice.py не найден")
        return False

    try:
        result = subprocess.run([sys.executable, str(script_path)],
                                capture_output=True, text=True, timeout=600)

        if result.returncode == 0:
            print("\n✅ LibreOffice успешно установлен!")
            return True
        else:
            print(f"\n❌ Ошибка установки: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("\n❌ Превышено время ожидания установки")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return False


def install_libreoffice():
    """Устанавливает LibreOffice (основная функция)"""
    print("\n" + "=" * 60)
    print("  Установка LibreOffice...")
    print("=" * 60)

    # Пробуем установить через скрипт
    print("\n🔄 Запуск установщика LibreOffice...")

    # Сначала пробуем через importlib
    success = install_libreoffice_via_script()

    # Если не получилось, пробуем через subprocess
    if not success:
        print("\n🔄 Пробуем альтернативный способ установки...")
        success = install_libreoffice_via_subprocess()

    return success


def show_manual_instructions():
    """Показывает инструкции для ручной установки"""
    os_name = get_os()

    print("\n" + "=" * 60)
    print("  Инструкция по ручной установке")
    print("=" * 60)

    if os_name == 'windows':
        print("""
📥 Установите LibreOffice вручную:

1. Скачайте установщик с официального сайта:
   https://www.libreoffice.org/download/download-libreoffice/

2. Запустите скачанный файл и следуйте инструкциям

3. После установки перезапустите приложение

Или используйте winget (если установлен):
   winget install LibreOffice.LibreOffice
""")
    elif os_name == 'macos':
        print("""
📥 Установите LibreOffice вручную:

1. Через Homebrew (рекомендуется):
   brew install --cask libreoffice

2. Или скачайте с официального сайта:
   https://www.libreoffice.org/download/download-libreoffice/

3. После установки перезапустите приложение
""")
    else:
        print("""
📥 Установите LibreOffice вручную:

Ubuntu/Debian:
   sudo apt update && sudo apt install -y libreoffice

Fedora/RHEL:
   sudo dnf install libreoffice

Arch Linux:
   sudo pacman -S libreoffice-fresh

После установки перезапустите приложение
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
        print("Ожидаемая структура:")
        print("  Convertator/")
        print("  ├── run.py")
        print("  ├── download_libreoffice.py")
        print("  ├── requirements.txt")
        print("  └── src/")
        print("      ├── main.py")
        print("      ├── gui/")
        print("      ├── converters/")
        print("      └── ...")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
