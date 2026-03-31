#!/usr/bin/env python3
"""
Скрипт для автоматического скачивания и установки LibreOffice из GitHub Releases
"""
import sys
import platform
import urllib.request
import tarfile
import zipfile
import shutil
from pathlib import Path

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
REPO_OWNER = "MiHoN135"
REPO_NAME = "Convertator-Releases"  # Публичный репозиторий с релизами
RELEASE_TAG = "v1.0.0"

# Определяем ОС
system = platform.system().lower()
if system == 'darwin':
    OS = 'macos'
elif system == 'windows':
    OS = 'windows'
else:
    OS = 'linux'


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
        print()
        return True
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return False


def get_download_url():
    """Возвращает URL для скачивания"""
    base = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{RELEASE_TAG}"

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


def extract_archive(archive_path, dest_dir):
    """Распаковывает архив"""
    print(f"📦 Распаковка {archive_path.name}...")

    if archive_path.suffix == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(dest_dir)
    else:
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(dest_dir)

    print(f"✅ Распаковано в {dest_dir}")


def main():
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка LibreOffice")
    print("=" * 60)

    project_root = Path(__file__).parent
    target = get_target_path(project_root)
    target.mkdir(parents=True, exist_ok=True)

    url = get_download_url()
    print(f"🔗 URL: {url}")

    # Скачиваем
    archive_path = project_root / "temp_download" / url.split('/')[-1]
    archive_path.parent.mkdir(exist_ok=True)

    if not download_file(url, archive_path):
        print("❌ Не удалось скачать")
        return False

    # Распаковываем
    extract_archive(archive_path, target)

    # Очищаем
    shutil.rmtree(archive_path.parent, ignore_errors=True)

    print("\n✅ LibreOffice успешно установлен!")
    return True


if __name__ == "__main__":
    main()