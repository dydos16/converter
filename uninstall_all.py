#!/usr/bin/env python3
"""
Скрипт для полного удаления File Converter Pro и всех зависимостей
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


def run_command(cmd, description="", check=False):
    """Выполняет команду и выводит результат"""
    if description:
        print(f"\n📦 {description}...")
    print(f"   {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ OK")
        else:
            if check:
                print(f"   ⚠️  Ошибка: {result.stderr.strip()[:200]}")
        return result
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return None


def main():
    print("=" * 60)
    print("  🗑️  Удаление File Converter Pro")
    print("=" * 60)
    print()

    print("ВНИМАНИЕ: Будут удалены:")
    print("  - Все Python библиотеки (PySide6, Pillow, pandas...)")
    print("  - LibreOffice")
    print("  - Настройки и логи")
    print()
    response = input("Напишите ДА чтобы продолжить: ")
    if response.strip() != 'ДА':
        print("Отмена.")
        return

    system = platform.system().lower()
    project_root = Path(__file__).parent

    # ============================================================
    # 1. Удаляем Python пакеты
    # ============================================================
    print("\n" + "-" * 60)
    print("  🐍 Удаление Python пакетов")
    print("-" * 60)

    packages = [
        'PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6',
        'loguru', 'Pillow', 'pillow-heif',
        'python-docx', 'python-pptx', 'reportlab',
        'PyMuPDF', 'pdf2image', 'pdfplumber', 'pdf2docx', 'pypdf',
        'openpyxl', 'pandas', 'tabula-py',
        'lxml', 'requests', 'colorama',
    ]

    pip_flags = ['--break-system-packages'] if system != 'windows' else []

    for pkg in packages:
        run_command(
            [sys.executable, '-m', 'pip', 'uninstall', '-y'] + pip_flags + [pkg],
            f"Удаление {pkg}"
        )

    remaining = [
        'fonttools', 'fire', 'termcolor', 'opencv-python-headless',
        'numpy', 'cffi', 'pycparser', 'charset-normalizer',
        'python-dateutil', 'six', 'et-xmlfile', 'XlsxWriter',
        'typing_extensions', 'pdfminer.six', 'pypdfium2',
        'distro', 'idna', 'urllib3', 'certifi', 'cryptography',
    ]

    for pkg in remaining:
        run_command(
            [sys.executable, '-m', 'pip', 'uninstall', '-y'] + pip_flags + [pkg],
            f"Удаление {pkg}"
        )

    print("\n🧹 Очистка кэша pip...")
    run_command([sys.executable, '-m', 'pip', 'cache', 'purge'])

    # ============================================================
    # 2. Удаляем LibreOffice
    # ============================================================
    print("\n" + "-" * 60)
    print("  📄 Удаление LibreOffice")
    print("-" * 60)

    # Удаляем встроенный
    lo_path = project_root / "resources" / "libreoffice"
    if lo_path.exists():
        shutil.rmtree(lo_path)
        print(f"✅ Удален встроенный LibreOffice: {lo_path}")

    # Удаляем скачанный
    app_path = Path.home() / "Library" / "Application Support" / "FileConverterPro" / "libreoffice"
    if app_path.exists():
        shutil.rmtree(app_path)
        print(f"✅ Удален скачанный LibreOffice: {app_path}")

    # Системный
    if system == 'darwin':
        run_command(['brew', 'uninstall', '--cask', 'libreoffice'], "brew uninstall libreoffice")
    elif system == 'linux':
        run_command(['sudo', 'apt', 'remove', '-y', 'libreoffice*'], "apt remove")
        run_command(['sudo', 'apt', 'autoremove', '-y'], "apt autoremove")

    # ============================================================
    # 3. Удаляем настройки и логи
    # ============================================================
    print("\n" + "-" * 60)
    print("  ⚙️  Удаление настроек и логов")
    print("-" * 60)

    config_dir = Path.home() / ".config" / "file-converter"
    if config_dir.exists():
        shutil.rmtree(config_dir)
        print(f"✅ Удалены настройки: {config_dir}")
    else:
        print(f"ℹ️  Настройки не найдены")

    # ============================================================
    # 4. Финальная проверка
    # ============================================================
    print("\n" + "=" * 60)
    print("  🔍 Проверка остатков")
    print("=" * 60)

    result = subprocess.run([sys.executable, '-m', 'pip', 'list'], capture_output=True, text=True)

    leftover = []
    for pkg in packages + remaining:
        if pkg.lower() in result.stdout.lower():
            leftover.append(pkg)

    if leftover:
        print(f"\n⚠️  Остались пакеты: {', '.join(leftover)}")
        print("Удалите их вручную если нужно.")
    else:
        print("\n✅ Все Python пакеты удалены")

    if system == 'darwin':
        if Path('/Applications/LibreOffice.app').exists():
            print("⚠️  Системный LibreOffice всё ещё в /Applications")
            print("   Удалите вручную через Finder если нужно.")
        else:
            print("✅ Системный LibreOffice удалён")

    print("\n" + "=" * 60)
    print("  🎉 Удаление завершено!")
    print("=" * 60)
    print()
    print("Можно удалить саму папку проекта:")
    print(f"   rm -rf {project_root}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)