"""
Менеджер для автоматической установки и использования LibreOffice
Поддержка Windows через pymsi
"""
import sys
import os
import platform
import subprocess
import shutil
import zipfile
import tarfile
import time
from pathlib import Path
from typing import Optional, Callable
from loguru import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Для Windows используем pymsi
if sys.platform == 'win32':
    try:
        import msilib
        MSI_AVAILABLE = True
    except ImportError:
        MSI_AVAILABLE = False
        logger.warning("pymsi не установлен. Установите: pip install pymsi")
else:
    MSI_AVAILABLE = False


class LibreOfficeManager:
    """Автоматическая установка и управление LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.setup_paths()
        self.version = "26.2.1"
        self.lang = "ru"

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
            paths = [
                Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                Path('/Applications/LibreOffice.app/Contents/MacOS/libreoffice'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    return True

        elif self.system == 'windows':
            paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    return True
        else:
            import shutil
            soffice = shutil.which('libreoffice') or shutil.which('soffice')
            if soffice:
                self.bin_path = Path(soffice)
                return True

        return False

    def get_download_urls(self) -> list:
        """Возвращает список рабочих ссылок для скачивания"""
        if self.system == 'darwin':
            return [
                f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
                f"https://ftp-osl.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/mac/x86_64/LibreOffice_{self.version}_MacOS_x86-64.dmg",
            ]
        elif self.system == 'windows':
            return [
                f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi",
                f"https://ftp-osl.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/win/x86_64/LibreOffice_{self.version}_Win_x86-64.msi",
            ]
        else:
            return [
                f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz",
                f"https://ftp-osl.osuosl.org/pub/libreoffice/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz",
            ]

    def download(self, progress_callback: Optional[Callable] = None) -> bool:
        """Скачивает LibreOffice с повторными попытками"""
        if not REQUESTS_AVAILABLE:
            logger.error("requests не установлен")
            return False

        urls = self.get_download_urls()
        filename = urls[0].split('/')[-1]
        filepath = self.base_dir / filename

        if filepath.exists():
            logger.info("Файл уже скачан")
            return True

        for url in urls:
            try:
                logger.info(f"Скачивание LibreOffice с {url}")

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                response = requests.get(url, stream=True, timeout=120, headers=headers, allow_redirects=True)
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
                logger.warning(f"Ошибка скачивания с {url}: {e}")
                continue

        logger.error("Не удалось скачать LibreOffice ни с одного зеркала")
        return False

    def install_windows_pymsi(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows через pymsi (распаковка MSI)"""
        try:
            if not MSI_AVAILABLE:
                logger.warning("pymsi не доступен, пробуем другой метод")
                return self.install_windows_msiexec(filepath, progress_callback)

            if progress_callback:
                progress_callback(30)

            import msilib
            import msilib.schema

            logger.info("Распаковка MSI через pymsi...")

            # Создаём папку для распаковки
            extract_dir = self.base_dir / "extract_msi"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            # Открываем MSI
            db = msilib.OpenDatabase(str(filepath), msilib.MSIDBOPEN_READONLY)

            # Извлекаем файлы
            view = db.OpenView("SELECT `File`, `FileName`, `Component_` FROM `File`")
            view.Execute(None)

            total_files = 0
            files = []
            while True:
                record = view.Fetch()
                if not record:
                    break
                file_id = record.GetString(1)
                file_name = record.GetString(2)
                component = record.GetString(3)
                files.append((file_id, file_name, component))
                total_files += 1

            if progress_callback:
                progress_callback(50)

            # Извлекаем файлы
            for i, (file_id, file_name, component) in enumerate(files):
                if progress_callback:
                    progress_callback(50 + int((i / max(total_files, 1)) * 40))

                # Получаем путь к файлу
                file_path = extract_dir / file_name
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Извлекаем файл
                view2 = db.OpenView(f"SELECT `Data` FROM `_Streams` WHERE `Name` = '{file_id}'")
                view2.Execute(None)
                record2 = view2.Fetch()
                if record2:
                    data = record2.GetString(1)
                    with open(file_path, 'wb') as f:
                        f.write(data.encode('latin1') if isinstance(data, str) else data)

            db.Close()

            if progress_callback:
                progress_callback(90)

            # Ищем soffice.exe
            found = False
            for root, dirs, files in os.walk(extract_dir):
                if 'soffice.exe' in files:
                    source = Path(root)
                    logger.info(f"Найден soffice.exe в: {source}")
                    if self.libreoffice_dir.exists():
                        shutil.rmtree(self.libreoffice_dir)
                    shutil.copytree(source, self.libreoffice_dir)
                    found = True
                    break

            # Удаляем временную папку
            shutil.rmtree(extract_dir, ignore_errors=True)

            if progress_callback:
                progress_callback(100)

            return found and self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки через pymsi: {e}")
            return False

    def install_windows_msiexec(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows через msiexec /a"""
        try:
            if progress_callback:
                progress_callback(30)

            extract_dir = self.base_dir / "extract_msi"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Распаковка MSI через msiexec...")

            cmd = ['msiexec', '/a', str(filepath), '/quiet', f'TARGETDIR={extract_dir}']
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=180)

            logger.info(f"msiexec завершён с кодом: {result.returncode}")

            if progress_callback:
                progress_callback(60)

            # Ищем soffice.exe
            found = False
            for root, dirs, files in os.walk(extract_dir):
                if 'soffice.exe' in files:
                    source = Path(root)
                    logger.info(f"Найден soffice.exe в: {source}")
                    if self.libreoffice_dir.exists():
                        shutil.rmtree(self.libreoffice_dir)
                    shutil.copytree(source, self.libreoffice_dir)
                    found = True
                    break

            shutil.rmtree(extract_dir, ignore_errors=True)

            if progress_callback:
                progress_callback(100)

            return found and self.is_installed()

        except Exception as e:
            logger.error(f"Ошибка установки через msiexec: {e}")
            return False

    def install_windows(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows"""
        # Пробуем pymsi
        if MSI_AVAILABLE:
            success = self.install_windows_pymsi(filepath, progress_callback)
            if success:
                return True

        # Если pymsi не сработал, пробуем msiexec
        return self.install_windows_msiexec(filepath, progress_callback)

    def install_macos(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на macOS"""
        try:
            mount_point = self.base_dir / "mnt"
            mount_point.mkdir(exist_ok=True)

            if progress_callback:
                progress_callback(50)

            subprocess.run(
                ['hdiutil', 'attach', str(filepath), '-mountpoint', str(mount_point)],
                capture_output=True, text=True, check=True
            )

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

            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(self.base_dir)

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

        if not self.download(progress_callback):
            return False

        url = self.get_download_urls()[0]
        filename = url.split('/')[-1]
        filepath = self.base_dir / filename

        if not filepath.exists():
            return False

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