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
import time
from pathlib import Path

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
REPO_OWNER = "MiHoN135"
REPO_NAME = "Convertator-Releases"
RELEASE_TAG = "v1.0.0"

# Определяем ОС и архитектуру
system = platform.system().lower()
arch = platform.machine().lower()

if system == 'darwin':
    OS = 'macos'
    if arch in ['arm64', 'aarch64']:
        ARCH = 'arm64'
    else:
        ARCH = 'x86_64'
elif system == 'windows':
    OS = 'windows'
    ARCH = 'x86_64'
else:
    OS = 'linux'
    ARCH = 'x86_64'


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
        if ARCH == 'arm64':
            return f"{base}/libreoffice_macos_arm64.tar.gz"
        else:
            return f"{base}/libreoffice_macos_x86_64.tar.gz"
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
# НАСТРОЙКА ДЛЯ macOS
# ============================================

def fix_macos_permissions(app_path):
    """Исправляет права и подпись для macOS приложения"""
    print("\n🔧 Настройка прав для macOS...")

    # 1. Снять карантин
    print("  Снятие карантина...")
    subprocess.run(['xattr', '-d', '-r', 'com.apple.quarantine', str(app_path)],
                   stderr=subprocess.DEVNULL)

    # 2. Дать права на выполнение
    print("  Установка прав...")
    subprocess.run(['chmod', '-R', '755', str(app_path)])

    # 3. Переподписать приложение
    print("  Переподпись приложения...")
    result = subprocess.run(
        ['codesign', '--force', '--deep', '--sign', '-', str(app_path)],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("  ✅ Подпись выполнена")
    else:
        # Пробуем без deep
        print("  Пробуем без deep...")
        result2 = subprocess.run(
            ['codesign', '--force', '--sign', '-', str(app_path)],
            capture_output=True, text=True
        )
        if result2.returncode == 0:
            print("  ✅ Подпись выполнена")
        else:
            print(f"  ⚠️  Предупреждение: {result2.stderr}")

    # 4. Проверка
    print("  Проверка...")
    soffice_path = app_path / "Contents" / "MacOS" / "soffice"
    if soffice_path.exists():
        result = subprocess.run([str(soffice_path), '--version'],
                                capture_output=True, timeout=10)

        if result.returncode == 0:
            print("  ✅ LibreOffice работает корректно")
            return True
        else:
            print(f"  ❌ LibreOffice не запускается: {result.stderr}")
            # Пробуем ещё раз переподписать
            print("  Повторная переподпись...")
            subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app_path)])
            return False

    return False

def install_macos(target_dir):
    """macOS: установка и настройка"""
    # Ищем .app
    app_path = target_dir / "LibreOffice.app"

    if not app_path.exists():
        # Может быть распаковано в подпапку
        for item in target_dir.iterdir():
            if item.is_dir() and item.name.endswith('.app'):
                app_path = item
                break

    if not app_path.exists():
        print("❌ LibreOffice.app не найден")
        return False

    print(f"✅ Найден LibreOffice.app в {app_path}")

    # Настраиваем права
    return fix_macos_permissions(app_path)


def install_windows(target_dir):
    """Windows: MSI файл, нужно распаковать при первом использовании"""
    msi_files = list(target_dir.glob("*.msi"))
    if not msi_files:
        print("❌ MSI файл не найден")
        return False

    print(f"✅ Windows MSI готов: {msi_files[0].name}")
    return True


def install_linux(target_dir):
    """Linux: устанавливаем DEB-пакеты"""
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

    deb_files = list(debs_path.glob("*.deb"))
    print(f"Найдено {len(deb_files)} DEB-пакетов")

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

        print("\n🔧 Исправление зависимостей...")
        subprocess.run(['sudo', 'apt', '--fix-broken', 'install', '-y'], capture_output=True)

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


def check_libreoffice_installed():
    """Проверяет, установлен ли LibreOffice"""
    project_root = Path(__file__).parent

    if OS == 'macos':
        app_path = project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app"
        if app_path.exists():
            # Проверяем, работает ли
            soffice = app_path / "Contents" / "MacOS" / "soffice"
            if soffice.exists():
                result = subprocess.run([str(soffice), '--version'], capture_output=True, timeout=5)
                return result.returncode == 0
        return False

    elif OS == 'windows':
        msi_path = project_root / "resources" / "libreoffice" / "windows" / "LibreOffice_26.2.2_Win_x86-64.msi"
        return msi_path.exists()

    else:
        import shutil
        if shutil.which('libreoffice') or shutil.which('soffice'):
            return True
        linux_dir = project_root / "resources" / "libreoffice" / "linux"
        return linux_dir.exists()


# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

def main():
    """Основная функция"""
    print("\n" + "=" * 60)
    print("  File Converter Pro - Установка LibreOffice")
    print("=" * 60)

    print(f"🖥️  ОС: {OS}")
    print(f"📐 Архитектура: {ARCH}")

    # Проверяем, не установлен ли уже LibreOffice
    if check_libreoffice_installed():
        print("✅ LibreOffice уже установлен и работает")
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