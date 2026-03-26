#!/usr/bin/env python3
"""
Запуск приложения с автоматической установкой зависимостей
"""
import sys
import time
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger


def show_progress(current, total, message):
    """Показывает прогресс установки"""
    percent = int((current / total) * 100)
    bar_length = 50
    filled = int(bar_length * current / total)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"\r[{bar}] {percent}% - {message}", end='', flush=True)


def main():
    """Запуск с проверкой зависимостей"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Проверка зависимостей")
    print("=" * 60 + "\n")

    try:
        # Импортируем менеджер зависимостей
        from src.core.dependency_manager import DependencyManager

        # Создаем менеджер
        manager = DependencyManager()

        # Проверяем зависимости
        print("📦 Проверка Python пакетов...")
        python_ok = manager.check_python_packages()

        print("\n📄 Проверка LibreOffice...")
        libreoffice_ok = manager.check_libreoffice()

        print("\n" + "-" * 60)

        # Если что-то не установлено, спрашиваем пользователя
        if not python_ok or not libreoffice_ok:
            print("\n⚠️  Необходимо установить отсутствующие компоненты:")

            if not python_ok:
                print(f"   - Python пакеты: {', '.join(manager.missing_packages)}")
            if not libreoffice_ok:
                print("   - LibreOffice (для конвертации Word и PowerPoint)")

            print("\n🔄 Автоматическая установка...")

            def progress_callback(current, total, message):
                show_progress(current, total, message)

            # Устанавливаем всё
            success = manager.install_all(progress_callback)
            print("\n")

            if not success:
                print("\n❌ Ошибка при установке зависимостей!")
                print("\nПопробуйте установить вручную:")
                print("  pip install -r requirements.txt")
                print("  brew install --cask libreoffice  # для macOS")
                sys.exit(1)

            print("\n✅ Все зависимости успешно установлены!")
            print("\n🔄 Перезапуск приложения...")
            time.sleep(2)

            # Перезапускаем приложение
            import subprocess
            subprocess.Popen([sys.executable, __file__])
            sys.exit(0)

        print("\n✅ Все зависимости установлены!")
        print("\n🚀 Запуск приложения...\n")

        # Запускаем основное приложение
        from src.main import main
        main()

    except ImportError as e:
        print(f"\n❌ Ошибка импорта: {e}")
        print("\nУстановите зависимости вручную:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()