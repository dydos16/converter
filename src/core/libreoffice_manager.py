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

# Импортируем requests только если нужно
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests не установлен. Для автоматической установки LibreOffice выполните: pip install requests")


class LibreOfficeManager:
    """Автоматическая установка и управление LibreOffice для macOS и Windows"""

    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.setup_paths()
        self.version = "7.6.7"  # Стабильная версия

    def setup_paths(self):
        """Настраивает пути для хранения LibreOffice"""
        if getattr(sys, 'frozen', False):
            # Запуск из собранного приложения
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            # Режим разработки
            self.base_dir = Path.home() / ".file-converter"

        self.libreoffice_dir = self.base_dir / "LibreOffice"
        self.bin_path = self.get_bin_path()

        # Создаем директорию если нужно
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
        Используем официальные зеркала
        """
        # Базовый URL с официального сайта
        base_url = "https://downloadarchive.documentfoundation.org/libreoffice/old"

        if self.system == 'darwin':
            # macOS - DMG файл
            url = f"{base_url}/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg"
            filename = f"LibreOffice_{self.version}_MacOS.dmg"
            extract_dir = "LibreOffice.app"
            installer_type = "dmg"

        elif self.system == 'windows':
            # Windows - MSI
            url = f"{base_url}/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi"
            filename = f"LibreOffice_{self.version}_Win.msi"
            extract_dir = "LibreOffice"
            installer_type = "msi"

        else:
            # Linux
            url = f"{base_url}/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz"
            filename = f"LibreOffice_{self.version}_Linux.tar.gz"
            extract_dir = "LibreOffice"
            installer_type = "tar"

        return url, filename, extract_dir, installer_type

    def download(self, progress_callback: Optional[Callable] = None) -> bool:
        """Скачивает LibreOffice"""
        if not REQUESTS_AVAILABLE:
            logger.error("requests не установлен")
            return False

        url, filename, _, _ = self.get_download_info()
        filepath = self.base_dir / filename

        # Если файл уже есть, не скачиваем
        if filepath.exists():
            logger.info(f"Файл уже скачан: {filepath}")
            return True

        try:
            logger.info(f"Скачивание LibreOffice с {url}")

            # Добавляем заголовки для обхода блокировок
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            response = requests.get(url, stream=True, timeout=60, headers=headers)

            # Если первая ссылка не работает, пробуем запасную
            if response.status_code != 200:
                logger.warning(f"Первая ссылка не работает, пробуем запасную...")
                # Запасные ссылки
                fallback_urls = [
                    f"https://ftp.osuosl.org/pub/libreoffice/libreoffice/old/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
                    f"https://mirror.yandex.ru/linux/libreoffice/libreoffice/old/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
                ]

                for fallback_url in fallback_urls:
                    if self.system == 'windows':
                        fallback_url = fallback_url.replace('mac/x86_64', 'win/x86_64').replace('.dmg', '.msi')
                    response = requests.get(fallback_url, stream=True, timeout=60, headers=headers)
                    if response.status_code == 200:
                        url = fallback_url
                        logger.info(f"Используем запасную ссылку: {url}")
                        break

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

            logger.info(f"Скачивание завершено: {filepath}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка скачивания: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return False

    def install_on_macos(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на macOS"""
        try:
            # Создаем временную папку для монтирования
            mount_point = self.base_dir / "mnt"
            mount_point.mkdir(exist_ok=True)

            # Монтируем DMG
            if progress_callback:
                progress_callback(50)
            logger.info("Монтирование DMG...")

            mount_result = subprocess.run(
                ['hdiutil', 'attach', str(filepath), '-mountpoint', str(mount_point)],
                capture_output=True,
                text=True
            )

            if mount_result.returncode != 0:
                raise Exception(f"Не удалось смонтировать DMG: {mount_result.stderr}")

            # Ищем приложение
            if progress_callback:
                progress_callback(70)
            logger.info("Копирование приложения...")

            app_source = mount_point / "LibreOffice.app"
            if not app_source.exists():
                # Ищем в других местах
                for item in mount_point.iterdir():
                    if item.name.endswith('.app'):
                        app_source = item
                        break

            if not app_source.exists():
                raise Exception("Не найден LibreOffice.app в DMG")

            # Удаляем старую версию
            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            # Копируем приложение
            shutil.copytree(app_source, self.libreoffice_dir)

            # Размонтируем
            if progress_callback:
                progress_callback(90)
            logger.info("Размонтирование...")
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)

            return True

        except Exception as e:
            logger.error(f"Ошибка установки на macOS: {e}")
            # Пытаемся размонтировать
            subprocess.run(['hdiutil', 'detach', mount_point], capture_output=True)
            return False

    def install_on_windows(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows"""
        try:
            # Создаем временную папку
            temp_dir = self.base_dir / "temp"
            temp_dir.mkdir(exist_ok=True)

            if progress_callback:
                progress_callback(50)
            logger.info("Распаковка MSI...")

            # Извлекаем MSI
            extract_cmd = [
                'msiexec', '/a', str(filepath),
                '/qb', f'TARGETDIR={str(temp_dir)}'
            ]

            result = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                shell=True
            )

            if result.returncode != 0:
                raise Exception(f"Ошибка распаковки MSI: {result.stderr}")

            # Ищем извлеченные файлы
            if progress_callback:
                progress_callback(70)
            logger.info("Поиск установленных файлов...")

            # Ищем папку LibreOffice в Program Files
            program_files = Path("C:/Program Files/LibreOffice")
            program_files_x86 = Path("C:/Program Files (x86)/LibreOffice")

            if program_files.exists():
                installed_dir = program_files
            elif program_files_x86.exists():
                installed_dir = program_files_x86
            else:
                # Ищем во временной папке
                extracted = list(temp_dir.glob("*LibreOffice*"))
                if extracted:
                    installed_dir = extracted[0]
                else:
                    raise Exception("Не найдена установленная версия LibreOffice")

            # Копируем в нашу папку
            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            shutil.copytree(installed_dir, self.libreoffice_dir)

            return True

        except Exception as e:
            logger.error(f"Ошибка установки на Windows: {e}")
            return False

    def install_on_linux(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Linux"""
        try:
            if progress_callback:
                progress_callback(50)
            logger.info("Распаковка архива...")

            # Распаковываем tar.gz
            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(self.base_dir)

            # Ищем извлеченную папку
            if progress_callback:
                progress_callback(70)
            logger.info("Поиск файлов...")

            extracted = list(self.base_dir.glob('LibreOffice_*'))[0]

            # Удаляем старую версию
            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            # Копируем
            extracted.rename(self.libreoffice_dir)

            # Делаем исполняемым
            if self.bin_path.exists():
                self.bin_path.chmod(0o755)

            return True

        except Exception as e:
            logger.error(f"Ошибка установки на Linux: {e}")
            return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Полная установка LibreOffice"""
        if self.is_installed():
            logger.info("LibreOffice уже установлен")
            return True

        # Скачиваем
        if not self.download(progress_callback):
            return False

        url, filename, _, installer_type = self.get_download_info()
        filepath = self.base_dir / filename

        if not filepath.exists():
            return False

        # Устанавливаем в зависимости от ОС
        if self.system == 'darwin':
            success = self.install_on_macos(filepath, progress_callback)
        elif self.system == 'windows':
            success = self.install_on_windows(filepath, progress_callback)
        else:
            success = self.install_on_linux(filepath, progress_callback)

        # Удаляем архив после успешной установки
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

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if progress_callback:
                progress_callback(80)

            # Проверяем результат
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)

                if progress_callback:
                    progress_callback(100)
                return output_path.exists()

            # Ищем PDF с другим именем
            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    return True

            logger.error(f"Ошибка конвертации: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации (5 минут)")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False