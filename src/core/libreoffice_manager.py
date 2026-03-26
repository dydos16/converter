"""
Менеджер для автоматической установки и использования LibreOffice
"""
import sys
import os
import platform
import subprocess
import zipfile
import tarfile
import shutil
import requests
from pathlib import Path
from loguru import logger


class LibreOfficeManager:
    """Автоматическая установка и управление LibreOffice"""

    def __init__(self):
        self.app_name = "File Converter Pro"
        self.setup_paths()

    def setup_paths(self):
        """Настраивает пути для хранения LibreOffice"""
        if getattr(sys, 'frozen', False):
            # Запуск из собранного приложения
            base = Path(sys.executable).parent
            if sys.platform == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            # Режим разработки
            self.base_dir = Path.home() / ".file-converter"

        self.libreoffice_dir = self.base_dir / "LibreOffice"
        self.bin_path = self.get_bin_path()

    def get_bin_path(self):
        """Возвращает путь к исполняемому файлу"""
        if sys.platform == 'darwin':
            return self.libreoffice_dir / "Contents" / "MacOS" / "soffice"
        elif sys.platform == 'win32':
            return self.libreoffice_dir / "program" / "soffice.exe"
        else:
            return self.libreoffice_dir / "program" / "soffice"

    def is_installed(self) -> bool:
        """Проверяет, установлен ли LibreOffice"""
        return self.bin_path.exists() and self.bin_path.is_file()

    def get_download_url(self) -> str:
        """Возвращает URL для скачивания LibreOffice"""
        system = platform.system().lower()
        arch = platform.machine().lower()

        if system == 'darwin':
            return "https://download.documentfoundation.org/libreoffice/stable/7.6.7/mac/x86_64/LibreOffice_7.6.7_MacOS_x86-64.dmg"
        elif system == 'windows':
            return "https://download.documentfoundation.org/libreoffice/stable/7.6.7/win/x86_64/LibreOffice_7.6.7_Win_x86-64.msi"
        else:  # linux
            return "https://download.documentfoundation.org/libreoffice/stable/7.6.7/linux/x86_64/LibreOffice_7.6.7_Linux_x86-64_rpm.tar.gz"

    def download(self, progress_callback=None) -> bool:
        """Скачивает LibreOffice"""
        url = self.get_download_url()
        filename = url.split('/')[-1]
        filepath = self.base_dir / filename

        self.base_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Скачивание LibreOffice с {url}")

            response = requests.get(url, stream=True)
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

            logger.info("Скачивание завершено")
            return True

        except Exception as e:
            logger.error(f"Ошибка скачивания: {e}")
            return False

    def extract(self, progress_callback=None) -> bool:
        """Распаковывает и устанавливает LibreOffice"""
        filename = self.get_download_url().split('/')[-1]
        filepath = self.base_dir / filename

        if not filepath.exists():
            return False

        try:
            logger.info("Распаковка LibreOffice...")

            if filename.endswith('.dmg'):
                # macOS DMG
                import subprocess
                mounted = subprocess.run(['hdiutil', 'attach', str(filepath)], capture_output=True)
                if mounted.returncode == 0:
                    import shutil
                    volume = Path('/Volumes/LibreOffice')
                    if volume.exists():
                        shutil.copytree(volume / 'LibreOffice.app', self.libreoffice_dir)
                    subprocess.run(['hdiutil', 'detach', volume])

            elif filename.endswith('.msi'):
                # Windows MSI
                cmd = f'msiexec /a "{filepath}" /qb TARGETDIR="{self.libreoffice_dir}"'
                subprocess.run(cmd, shell=True)

            elif filename.endswith('.tar.gz'):
                # Linux tar.gz
                with tarfile.open(filepath, 'r:gz') as tar:
                    tar.extractall(self.base_dir)
                # Ищем извлеченную папку
                extracted = list(self.base_dir.glob('LibreOffice_*'))[0]
                extracted.rename(self.libreoffice_dir)

            # Делаем исполняемым
            if sys.platform != 'win32':
                self.bin_path.chmod(0o755)

            # Удаляем архив
            filepath.unlink()

            logger.info("Распаковка завершена")
            return True

        except Exception as e:
            logger.error(f"Ошибка распаковки: {e}")
            return False

    def install(self, progress_callback=None) -> bool:
        """Полная установка LibreOffice"""
        if self.is_installed():
            logger.info("LibreOffice уже установлен")
            return True

        if not self.download(progress_callback):
            return False

        return self.extract(progress_callback)

    def convert(self, input_path: Path, output_path: Path, progress_callback=None) -> bool:
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists() and expected_pdf != output_path:
                expected_pdf.rename(output_path)

            return output_path.exists()

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False