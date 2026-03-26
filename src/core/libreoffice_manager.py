"""
Менеджер для автоматической установки и использования LibreOffice
Поддержка macOS и Windows
"""
import sys
import os
import platform
import subprocess
import zipfile
import tarfile
import shutil
import time
from pathlib import Path
from typing import Optional, Callable
from loguru import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests не установлен")


class LibreOfficeManager:
    """Автоматическая установка и управление LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.setup_paths()
        self.version = "7.6.7"  # Стабильная версия

    def setup_paths(self):
        """Настраивает пути для хранения LibreOffice"""
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            self.base_dir = Path.home() / ".file-converter"

        self.libreoffice_dir = self.base_dir / "LibreOffice"
        self.bin_path = self.get_bin_path()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_bin_path(self) -> Path:
        """Возвращает путь к исполняемому файлу LibreOffice"""
        if self.system == 'darwin':
            return self.libreoffice_dir / "Contents" / "MacOS" / "soffice"
        elif self.system == 'windows':
            return self.libreoffice_dir / "program" / "soffice.exe"
        else:
            return self.libreoffice_dir / "program" / "soffice"

    def is_installed(self) -> bool:
        """Проверяет, установлен ли LibreOffice"""
        return self.bin_path.exists() and self.bin_path.is_file()

    def get_download_info(self) -> tuple:
        """
        Возвращает (url, filename, extract_dir, installer_type)
        Используем рабочие ссылки
        """
        if self.system == 'darwin':
            # macOS - DMG
            url = f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg"
            filename = f"LibreOffice_{self.version}_MacOS.dmg"
            extract_dir = "LibreOffice.app"
            installer_type = "dmg"

        elif self.system == 'windows':
            # Windows - MSI
            url = f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi"
            filename = f"LibreOffice_{self.version}_Win.msi"
            extract_dir = "LibreOffice"
            installer_type = "msi"

        else:
            # Linux
            url = f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz"
            filename = f"LibreOffice_{self.version}_Linux.tar.gz"
            extract_dir = "LibreOffice"
            installer_type = "tar"

        return url, filename, extract_dir, installer_type

    def get_fallback_urls(self) -> list:
        """Возвращает список запасных ссылок"""
        if self.system == 'darwin':
            return [
                f"https://ftp.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
                f"https://mirror.accum.se/mirror/libreoffice.org/stable/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
            ]
        elif self.system == 'windows':
            return [
                f"https://ftp.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi",
                f"https://sourceforge.net/projects/libreoffice.mirror/files/stable/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi/download",
            ]
        else:
            return [
                f"https://ftp.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz",
            ]

    def download(self, progress_callback: Optional[Callable] = None) -> bool:
        """Скачивает LibreOffice"""
        if not REQUESTS_AVAILABLE:
            logger.error("requests не установлен")
            return False

        url, filename, _, _ = self.get_download_info()
        filepath = self.base_dir / filename

        if filepath.exists():
            logger.info(f"Файл уже скачан: {filepath}")
            return True

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Пробуем основную ссылку
        try:
            logger.info(f"Скачивание LibreOffice...")
            response = requests.get(url, stream=True, timeout=30, headers=headers)

            if response.status_code != 200:
                logger.warning(f"Основная ссылка не работает (404), пробуем запасные...")
                # Пробуем запасные ссылки
                for fallback_url in self.get_fallback_urls():
                    logger.info(f"Пробуем: {fallback_url}")
                    response = requests.get(fallback_url, stream=True, timeout=30, headers=headers)
                    if response.status_code == 200:
                        url = fallback_url
                        logger.info(f"Используем запасную ссылку")
                        break
                else:
                    raise Exception("Все ссылки не работают")

            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress)

            logger.info(f"Скачивание завершено")
            return True

        except Exception as e:
            logger.error(f"Ошибка скачивания: {e}")
            return False

    def install_on_macos(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на macOS"""
        try:
            mount_point = self.base_dir / "mnt"
            mount_point.mkdir(exist_ok=True)

            if progress_callback:
                progress_callback(50)

            # Монтируем DMG
            result = subprocess.run(
                ['hdiutil', 'attach', str(filepath), '-mountpoint', str(mount_point)],
                capture_output=True, text=True
            )

            if result.returncode != 0:
                raise Exception(f"Ошибка монтирования: {result.stderr}")

            # Ищем приложение
            app_source = mount_point / "LibreOffice.app"
            if not app_source.exists():
                for item in mount_point.iterdir():
                    if item.name.endswith('.app'):
                        app_source = item
                        break

            if not app_source.exists():
                raise Exception("LibreOffice.app не найден")

            # Копируем
            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            shutil.copytree(app_source, self.libreoffice_dir)

            # Размонтируем
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)

            return True

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)
            return False

    def install_on_windows(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows"""
        try:
            temp_dir = self.base_dir / "temp"
            temp_dir.mkdir(exist_ok=True)

            if progress_callback:
                progress_callback(50)

            # Тихая установка MSI
            install_cmd = [
                'msiexec', '/i', str(filepath),
                '/quiet', '/qn', '/norestart',
                f'INSTALLDIR="{self.libreoffice_dir}"'
            ]

            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=300
            )

            if result.returncode != 0:
                # Пробуем распаковать без установки
                extract_cmd = [
                    'msiexec', '/a', str(filepath),
                    '/quiet', f'TARGETDIR={temp_dir}'
                ]
                result = subprocess.run(extract_cmd, capture_output=True, text=True, shell=True)

                if result.returncode == 0:
                    # Копируем из временной папки
                    source = temp_dir / "PFiles" / "LibreOffice"
                    if not source.exists():
                        source = temp_dir / "LibreOffice"
                    if source.exists():
                        shutil.copytree(source, self.libreoffice_dir)

            return self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Полная установка LibreOffice"""
        if self.is_installed():
            return True

        if not self.download(progress_callback):
            return False

        _, filename, _, _ = self.get_download_info()
        filepath = self.base_dir / filename

        if not filepath.exists():
            return False

        if self.system == 'darwin':
            success = self.install_on_macos(filepath, progress_callback)
        elif self.system == 'windows':
            success = self.install_on_windows(filepath, progress_callback)
        else:
            success = False

        if success and filepath.exists():
            try:
                filepath.unlink()
            except:
                pass

        return success

    def convert(self, input_path: Path, output_path: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Конвертирует файл через LibreOffice"""
        if not self.is_installed():
            if not self.install(progress_callback):
                return False

        cmd = [
            str(self.bin_path),
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        try:
            if progress_callback:
                progress_callback(50)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if progress_callback:
                progress_callback(80)

            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                return output_path.exists()

            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    return True

            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False