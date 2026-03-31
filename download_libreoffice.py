#!/usr/bin/env python3
"""
Скрипт для автоматического скачивания и установки LibreOffice из GitHub Releases
"""
import os
import sys
import platform
import urllib.request
import tarfile
import zipfile
import shutil
import time
from pathlib import Path

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
REPO_OWNER = "MiHoN135"
REPO_NAME = "Convertator"
RELEASE_TAG = "1.0.0"  # Тег релиза (без v)

# Определяем ОС
system = platform.system().lower()
if system == 'darwin':
    OS = 'macos'
elif system == 'windows':
    OS = 'windows'
else:
    OS = 'linux'


# ============================================
# ФУНКЦИИ
# ============================================

def download_file(url, dest):
    """Скачивает файл с отображением прогресса"""
    print(f"\n📥 Скачивание {url.split('/')[-1]}...")

    def report(block_num, block_size, total_size):
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        percent = int(downloaded / total_size * 100)
        bar = '█' * int(percent / 2) + '░' * (50 - int(percent / 2))
        mb_downloaded = downloaded / 1024 / 1024
        mb_total = total_size / 1024 / 1024
        print(f"\r[{bar}] {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='', flush=True)

    try:
        urllib.request.urlretrieve(url, dest, reporthook=report)
        print()  # Новая строка после прогресса
        return True
    except Exception as e:
        print(f"\n❌ Ошибка скачивания: {e}")
        return False


def extract_archive(archive_path, dest_dir):
    """Распаковывает архив"""
    print(f"📦 Распаковка {archive_path.name}...")

    try:
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(dest_dir)
        else:  # .tar.gz
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(dest_dir)
        print(f"✅ Распаковано в {dest_dir}")
        return True
    except Exception as e:
        print(f"❌ Ошибка распаковки: {e}")
        return False


def get_download_url(version):
    """Возвращает URL для скачивания"""
    base = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{version}"

    if OS == 'macos':
        return f"{base}/libreoffice_macos.tar.gz"
    elif OS == 'windows':
        return f"{base}/libreoffice_windows.zip"
    else:
        return f"{base}/libreoffice_linux.tar.gz"


def get_target_path(project_root):
    """Возвращает путь, куда нужно распаковать"""
    resources_dir = project_root / "resources" / "libreoffice"

    if OS == 'macos':
        return resources_dir / "macos"
    elif OS == 'windows':
        return resources_dir / "windows"
    else:
        return resources_dir / "linux"


def check_existing(project_root):
    """Проверяет, установлен ли уже LibreOffice"""
    target = get_target_path(project_root)

    if OS == 'macos':
        return (target / "LibreOffice.app").exists()
    elif OS == 'windows':
        # Проверяем MSI файл или распакованную версию
        if (target / "LibreOffice_26.2.2_Win_x86-64.msi").exists():
            return True
        if (target / "LibreOffice" / "program" / "soffice.exe").exists():
            return True
        return False
    else:
        # Linux
        if (target / "LibreOffice_26.2.2.2_Linux_x86-64_deb").exists():
            return True
        if (target / "LibreOffice" / "program" / "soffice").exists():
            return True
        return False


def get_archive_name():
    """Возвращает имя архива для текущей ОС"""
    if OS == 'macos':
        return "libreoffice_macos.tar.gz"
    elif OS == 'windows':
        return "libreoffice_windows.zip"
    else:
        return "libreoffice_linux.tar.gz"


def main():
    """Основная функция"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка LibreOffice")
    print("=" * 60)

    # Определяем корень проекта (родительская папка этого скрипта)
    project_root = Path(__file__).parent

    print(f"📁 Проект: {project_root}")
    print(f"🖥️  ОС: {OS}")

    # Проверяем, нужно ли устанавливать
    if check_existing(project_root):
        print("✅ LibreOffice уже установлен")
        return True

    # Создаём папки
    target = get_target_path(project_root)
    target.mkdir(parents=True, exist_ok=True)

    # Получаем URL для скачивания
    url = get_download_url(RELEASE_TAG)
    print(f"🔗 URL: {url}")

    # Создаём временную папку для скачивания
    temp_dir = project_root / "temp_download"
    temp_dir.mkdir(exist_ok=True)

    archive_name = get_archive_name()
    archive_path = temp_dir / archive_name

    # Скачиваем архив
    print(f"\n📥 Начинаем скачивание {archive_name}...")
    if not download_file(url, archive_path):
        print("\n❌ Не удалось скачать архив")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    # Проверяем размер файла
    size_mb = archive_path.stat().st_size / 1024 / 1024
    print(f"✅ Скачано {size_mb:.1f} MB")

    # Распаковываем
    print("\n📦 Распаковка...")
    if not extract_archive(archive_path, target):
        print("❌ Ошибка распаковки")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    # Удаляем временную папку
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Для Windows: MSI нужно распаковать при первом использовании
    if OS == 'windows':
        print("\n💡 Примечание: MSI файл будет распакован при первом запуске конвертации")

    print("\n✅ LibreOffice успешно установлен!")
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)