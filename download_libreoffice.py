#!/usr/bin/env python3
"""
Скрипт для автоматического скачивания и установки LibreOffice из GitHub Releases
"""
import sys
import os
import platform
import urllib.request
import tarfile
import zipfile
import shutil
import subprocess
from pathlib import Path

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
REPO_OWNER = "MiHoN135"
REPO_NAME = "Convertator-Releases"
RELEASE_TAG = "v1.0.0"

# Определяем ОС
system = platform.system().lower()
if system == 'darwin':
    OS = 'macos'
elif system == 'windows':
    OS = 'windows'
else:
    OS = 'linux'


# ============================================
# ФУНКЦИИ СКАЧИВАНИЯ
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


# ============================================
# УСТАНОВКА ДЛЯ РАЗНЫХ ОС
# ============================================

def install_macos(target_dir):
    """macOS: уже готовый .app, ничего не делаем"""
    app_path = target_dir / "LibreOffice.app"
    if app_path.exists():
        print("✅ macOS версия готова")
        return True
    return False


def install_windows(target_dir):
    """Windows: MSI файл, нужно распаковать при первом использовании"""
    msi_files = list(target_dir.glob("*.msi"))
    if msi_files:
        print(f"✅ Windows MSI готов: {msi_files[0].name}")
        return True
    return False


def install_linux(target_dir):
    """Linux: устанавливаем DEB-пакеты"""
    # Ищем папку с DEBS
    deb_dirs = list(target_dir.glob("*_Linux_x86-64_deb"))
    if not deb_dirs:
        deb_dirs = list(target_dir.glob("LibreOffice_*"))

    if not deb_dirs:
        print("❌ Не найдена папка с DEB-пакетами")
        return False

    deb_dir = deb_dirs[0]
    debs_path = deb_dir / "DEBS"

    if not debs_path.exists():
        print(f"❌ Папка DEBS не найдена: {debs_path}")
        return False

    print("📦 Установка DEB-пакетов LibreOffice...")

    # Получаем список всех .deb файлов
    deb_files = list(debs_path.glob("*.deb"))
    if not deb_files:
        print("❌ Нет DEB-файлов для установки")
        return False

    print(f"Найдено {len(deb_files)} DEB-пакетов")

    # Устанавливаем пакеты по одному
    try:
        for deb_file in deb_files:
            print(f"  Установка {deb_file.name}...")
            result = subprocess.run(
                ['sudo', 'dpkg', '-i', str(deb_file)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"    Ошибка: {result.stderr}")

        # Исправляем зависимости
        print("\n🔧 Исправление зависимостей...")
        subprocess.run(['sudo', 'apt', '--fix-broken', 'install', '-y'], capture_output=True)

        # Проверяем, что установилось
        import shutil
        if shutil.which('soffice') or shutil.which('libreoffice'):
            print("✅ LibreOffice успешно установлен")
            return True
        else:
            print("⚠️  LibreOffice установлен, но не найден в PATH")
            return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def install_system_linux():
    """Установка LibreOffice через apt (запасной вариант)"""
    print("📦 Установка LibreOffice через apt...")
    try:
        subprocess.run(['sudo', 'apt', 'update'], capture_output=True)
        result = subprocess.run(['sudo', 'apt', 'install', '-y', 'libreoffice'], capture_output=True)
        if result.returncode == 0:
            print("✅ LibreOffice установлен через apt")
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

def check_libreoffice_installed():
    """Проверяет, установлен ли LibreOffice в системе"""
    import shutil

    if shutil.which('libreoffice'):
        return True
    if shutil.which('soffice'):
        return True

    # Для macOS проверяем Applications
    if OS == 'macos':
        if Path('/Applications/LibreOffice.app').exists():
            return True

    # Для Windows проверяем Program Files
    if OS == 'windows':
        if Path('C:/Program Files/LibreOffice').exists() or \
                Path('C:/Program Files (x86)/LibreOffice').exists():
            return True

    return False


def main():
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка LibreOffice")
    print("=" * 60)

    # Сначала проверяем, не установлен ли уже LibreOffice
    if check_libreoffice_installed():
        print("✅ LibreOffice уже установлен в системе")
        return True

    project_root = Path(__file__).parent
    target = get_target_path(project_root)
    target.mkdir(parents=True, exist_ok=True)

    # Для Linux сначала пробуем установить через apt
    if OS == 'linux':
        print("\n🔄 Пробуем установить через системный менеджер...")
        if install_system_linux():
            return True

    # Скачиваем архив
    url = get_download_url()
    print(f"\n🔗 URL: {url}")

    archive_path = project_root / "temp_download" / url.split('/')[-1]
    archive_path.parent.mkdir(exist_ok=True)

    if not download_file(url, archive_path):
        print("❌ Не удалось скачать архив")
        return False

    # Распаковываем
    extract_archive(archive_path, target)

    # Устанавливаем в зависимости от ОС
    if OS == 'macos':
        success = install_macos(target)
    elif OS == 'windows':
        success = install_windows(target)
    else:
        success = install_linux(target)

    # Очищаем временную папку
    shutil.rmtree(archive_path.parent, ignore_errors=True)

    if success:
        print("\n✅ LibreOffice успешно установлен!")
        return True
    else:
        print("\n❌ Не удалось установить LibreOffice")
        return False


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