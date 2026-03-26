"""
Менеджер для автоматической установки LibreOffice
"""
import sys
import os
import platform
import subprocess
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


class LibreOfficeManager:
    """Автоматическая установка и управление LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self.setup_paths()

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
        if self.bin_path.exists():
            return True

        # Проверяем системную установку
        if self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                return True
        elif self.system == 'windows':
            if Path('C:/Program Files/LibreOffice/program/soffice.exe').exists() or \
               Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe').exists():
                return True
        else:
            if shutil.which('libreoffice') or shutil.which('soffice'):
                return True

        return False

    def get_download_url(self) -> str:
        """Возвращает рабочую ссылку для скачивания"""
        if self.system == 'darwin':
            return "https://www.libreoffice.org/donate/dl/mac-x86_64/26.2.1/ru/LibreOffice_26.2.1_MacOS_x86-64.dmg"
        elif self.system == 'windows':
            return "https://www.libreoffice.org/donate/dl/win-x86_64/26.2.1/ru/LibreOffice_26.2.1_Win_x86-64.msi"
        else:
            return "https://www.libreoffice.org/donate/dl/linux-x86_64/26.2.1/ru/LibreOffice_26.2.1_Linux_x86-64_rpm.tar.gz"

    def download(self, progress_callback: Optional[Callable] = None) -> bool:
        """Скачивает LibreOffice"""
        if not REQUESTS_AVAILABLE:
            logger.error("requests не установлен")
            return False

        url = self.get_download_url()
        filename = url.split('/')[-1]
        filepath = self.base_dir / filename

        if filepath.exists():
            logger.info("Файл уже скачан")
            return True

        try:
            logger.info("Скачивание LibreOffice...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, stream=True, timeout=60, headers=headers, allow_redirects=True)
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

            logger.info("Скачивание завершено")
            return True

        except Exception as e:
            logger.error(f"Ошибка скачивания: {e}")
            return False

    def install_windows(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows"""
        try:
            if progress_callback:
                progress_callback(50)

            # Создаём папку назначения
            self.libreoffice_dir.mkdir(parents=True, exist_ok=True)

            # Тихая установка MSI
            cmd = [
                'msiexec', '/i', str(filepath),
                '/quiet', '/qn', '/norestart',
                f'INSTALLDIR="{self.libreoffice_dir}"'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=300)

            if progress_callback:
                progress_callback(100)

            # Проверяем, что установка прошла успешно
            return self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            return False

    def install_macos(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на macOS"""
        try:
            mount_point = self.base_dir / "mnt"
            mount_point.mkdir(exist_ok=True)

            if progress_callback:
                progress_callback(50)

            # Монтируем DMG
            subprocess.run(
                ['hdiutil', 'attach', str(filepath), '-mountpoint', str(mount_point)],
                capture_output=True, text=True, check=True
            )

            # Копируем приложение
            app_source = mount_point / "LibreOffice.app"
            if not app_source.exists():
                for item in mount_point.iterdir():
                    if item.name.endswith('.app'):
                        app_source = item
                        break

            if not app_source.exists():
                raise Exception("LibreOffice.app не найден")

            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            shutil.copytree(app_source, self.libreoffice_dir)

            # Размонтируем
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)

            if progress_callback:
                progress_callback(100)

            return self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)
            return False

    def install_linux(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Linux"""
        try:
            if progress_callback:
                progress_callback(50)

            import tarfile
            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(self.base_dir)

            # Ищем извлечённую папку
            extracted = list(self.base_dir.glob('LibreOffice_*'))[0]

            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            extracted.rename(self.libreoffice_dir)

            if self.bin_path.exists():
                self.bin_path.chmod(0o755)

            if progress_callback:
                progress_callback(100)

            return self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки: {e}")
            return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Полная установка LibreOffice"""
        if self.is_installed():
            logger.info("LibreOffice уже установлен")
            return True

        # Скачиваем
        if not self.download(progress_callback):
            logger.error("Не удалось скачать LibreOffice")
            return False

        url = self.get_download_url()
        filename = url.split('/')[-1]
        filepath = self.base_dir / filename

        if not filepath.exists():
            return False

        # Устанавливаем в зависимости от ОС
        if self.system == 'darwin':
            success = self.install_macos(filepath, progress_callback)
        elif self.system == 'windows':
            success = self.install_windows(filepath, progress_callback)
        else:
            success = self.install_linux(filepath, progress_callback)

        # Удаляем файл установки после успеха
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

        # Путь к исполняемому файлу
        bin_path = self.bin_path

        if not bin_path.exists():
            return False

        cmd = [
            str(bin_path),
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
                return True

            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False