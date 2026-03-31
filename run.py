#!/usr/bin/env python3
"""
Запуск приложения
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("\n" + "=" * 60)
    print("  File Converter Pro")
    print("=" * 60 + "\n")

    # Проверяем встроенный LibreOffice
    try:
        from src.core.libreoffice_manager import LibreOfficeManager
        manager = LibreOfficeManager()

        if manager.is_installed():
            print("✅ LibreOffice готов к работе")
        else:
            print("❌ LibreOffice не найден")
            print("\nПоместите LibreOffice.app в папку:")
            print("  resources/libreoffice/macos/")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

    print("\n🚀 Запуск приложения...\n")

    try:
        from src.main import main
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()