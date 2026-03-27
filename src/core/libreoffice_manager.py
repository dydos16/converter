"""
Менеджер для автоматической установки и использования LibreOffice
"""
import sys
import os
import platform
import subprocess
import shutil
import tarfile
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
        self.arch = platform.machine().lower()
        self.setup_paths()
        self.version = "25.8.5"

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
        # Проверяем встроенную версию
        if self.bin_path.exists():
            logger.info(f"Найден LibreOffice в: {self.bin_path}")
            return True

        # Проверяем системную установку
        if self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                self.bin_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                return True
        elif self.system == 'windows':
            # Проверяем Program Files
            paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    logger.info(f"Найден LibreOffice в системе: {self.bin_path}")
                    return True

            # Проверяем распакованную версию в .file-converter (поиск по всем папкам)
            if self.libreoffice_dir.exists():
                for root, dirs, files in os.walk(self.libreoffice_dir):
                    if 'soffice.exe' in files:
                        self.bin_path = Path(root) / 'soffice.exe'
                        logger.info(f"Найден LibreOffice в .file-converter: {self.bin_path}")
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
                f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_deb.tar.gz",
                f"https://download.documentfoundation.org/libreoffice/stable/{self.version}/linux/x86_64/LibreOffice_{self.version}_Linux_x86-64_rpm.tar.gz",
            ]

    def download(self, progress_callback: Optional[Callable] = None) -> bool:
        """Скачивает LibreOffice"""
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
                logger.info("Скачивание LibreOffice...")

                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(url, stream=True, timeout=120, headers=headers, allow_redirects=True)

                if response.status_code == 404:
                    logger.warning(f"Ссылка не найдена (404), пробуем следующую...")
                    continue

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
                logger.warning(f"Ошибка скачивания: {e}")
                continue

        logger.error("Не удалось скачать LibreOffice ни с одного зеркала")
        return False

    def install_windows(self, filepath: Path, progress_callback=None) -> bool:
        """Установка на Windows - распаковка MSI"""
        try:
            if progress_callback:
                progress_callback(30)

            extract_dir = self.base_dir / "extract_msi"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Распаковка MSI...")

            cmd = ['msiexec', '/a', str(filepath), '/quiet', f'TARGETDIR={extract_dir}']
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=180)

            logger.info(f"msiexec завершён с кодом: {result.returncode}")

            if progress_callback:
                progress_callback(60)

            # Ищем папку program
            program_dir = None
            for root, dirs, files in os.walk(extract_dir):
                if 'soffice.exe' in files:
                    program_dir = Path(root)
                    logger.info(f"Найден soffice.exe в: {program_dir}")
                    break

            if program_dir:
                # Копируем всю папку, содержащую program
                if program_dir.name == 'program':
                    # Копируем родительскую папку
                    parent = program_dir.parent
                    shutil.copytree(parent, self.libreoffice_dir)
                else:
                    shutil.copytree(program_dir, self.libreoffice_dir)

                logger.info(f"LibreOffice скопирован в: {self.libreoffice_dir}")

            shutil.rmtree(extract_dir, ignore_errors=True)

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
        """Установка на Linux из архива"""
        try:
            if progress_callback:
                progress_callback(50)

            extract_dir = self.base_dir / "extract_linux"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Распаковка архива...")

            with tarfile.open(filepath, 'r:gz') as tar:
                tar.extractall(extract_dir)

            if progress_callback:
                progress_callback(70)

            # Ищем папку с программой
            extracted = None
            for item in extract_dir.iterdir():
                if item.is_dir() and 'LibreOffice' in item.name:
                    extracted = item
                    break

            if not extracted:
                for root, dirs, files in os.walk(extract_dir):
                    for dir_name in dirs:
                        if 'LibreOffice' in dir_name:
                            extracted = Path(root) / dir_name
                            break
                    if extracted:
                        break

            if not extracted:
                raise Exception("Не найдена папка LibreOffice")

            # Копируем в целевую папку
            if self.libreoffice_dir.exists():
                shutil.rmtree(self.libreoffice_dir)

            shutil.copytree(extracted, self.libreoffice_dir)

            if self.bin_path.exists():
                self.bin_path.chmod(0o755)

            shutil.rmtree(extract_dir, ignore_errors=True)

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
            logger.error(f"LibreOffice не найден по пути: {bin_path}")
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

            # Ищем PDF с другим именем
            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    return True

            logger.error(f"PDF не создан. stderr: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False