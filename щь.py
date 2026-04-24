#!/usr/bin/env python3
"""
Скрипт для удаления File Converter Pro и всех зависимостей
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=False):
    """Выполняет команду в терминале"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"⚠️  Ошибка: {result.stderr}")
        return result
    except Exception as e:
        print(f"⚠️  Ошибка: {e}")
        return None


def main():
    print("=" * 60)
    print("  Удаление File Converter Pro и всех зависимостей")
    print("=" * 60)

    # 1. Удаление Python библиотек
    print("\n📦 Удаление Python библиотек...")
    packages = [
        "PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6",
        "python-docx", "python-pptx", "reportlab", "Pillow", "openpyxl",
        "loguru", "colorama", "requests", "lxml"
    ]

    for pkg in packages:
        cmd = f"pip3 uninstall {pkg} -y --break-system-packages"
        print(f"   Удаление {pkg}...")
        run_command(cmd)

    # 2. Удаление LibreOffice (через brew)
    print("\n📄 Удаление LibreOffice (через brew)...")
    run_command("brew uninstall --cask libreoffice 2>/dev/null || true")
    run_command("brew uninstall libreoffice 2>/dev/null || true")

    # 3. Удаление папки с загруженным LibreOffice
    print("\n🗑️  Удаление папки ~/.file-converter...")
    file_converter_dir = Path.home() / ".file-converter"
    if file_converter_dir.exists():
        shutil.rmtree(file_converter_dir)
        print(f"   Удалена {file_converter_dir}")
    else:
        print(f"   {file_converter_dir} не найдена")

    # 4. Удаление папки с настройками
    print("\n🗑️  Удаление папки ~/.config/file-converter...")
    config_dir = Path.home() / ".config" / "file-converter"
    if config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"   Удалена {config_dir}")
    else:
        print(f"   {config_dir} не найдена")

    # 5. Очистка кэша pip
    print("\n🧹 Очистка кэша pip...")
    run_command("pip3 cache purge")

    # 6. Проверка остатков
    print("\n" + "=" * 60)
    print("  Проверка остатков")
    print("=" * 60)

    print("\nОставшиеся Python пакеты:")
    result = run_command(
        "pip3 list | grep -E 'PySide6|python-docx|python-pptx|reportlab|Pillow|openpyxl|loguru|colorama|requests|lxml'")
    if result and result.stdout.strip():
        print(result.stdout)
    else:
        print("  ✅ Ничего не найдено")

    print("\nОставшиеся папки:")
    if file_converter_dir.exists():
        print(f"  ⚠️  {file_converter_dir} всё ещё существует")
    if config_dir.exists():
        print(f"  ⚠️  {config_dir} всё ещё существует")

    print("\n" + "=" * 60)
    print("  Удаление завершено!")
    print("=" * 60)


if __name__ == "__main__":
    main()