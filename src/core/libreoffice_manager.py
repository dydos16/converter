"""
Менеджер для использования встроенной версии LibreOffice
"""
import sys
import platform
import subprocess
import shutil
import os
from pathlib import Path
from typing import Optional, Callable
from loguru import logger


class LibreOfficeManager:
    """Использование встроенной версии LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self.setup_paths()

    def setup_paths(self):
        """Настраивает пути к встроенному LibreOffice"""
        # Определяем корневую директорию проекта
        if getattr(sys, 'frozen', False):
            # Запуск из собранного приложения
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            # Режим разработки
            base = Path(__file__).parent.parent.parent
            self.base_dir = base / "resources"

        # Путь к встроенному LibreOffice в зависимости от ОС
        if self.system == 'darwin':
            self.bin_path = self.base_dir / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
        elif self.system == 'windows':
            # Для Windows сначала пробуем распакованную версию
            extracted_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice"
            if extracted_path.exists():
                self.bin_path = extracted_path / "program" / "soffice.exe"
            else:
                # Или MSI файл (нужно будет распаковать при первом запуске)
                self.msi_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice_26.2.2_Win_x86-64.msi"
                self.bin_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        else:
            # Linux
            self.bin_path = self.base_dir / "libreoffice" / "linux" / "LibreOffice" / "program" / "soffice"

        logger.info(f"Путь к LibreOffice: {self.bin_path}")

    def extract_windows(self) -> bool:
        """Распаковывает MSI на Windows"""
        if not hasattr(self, 'msi_path') or not self.msi_path.exists():
            return False

        try:
            extract_dir = self.base_dir / "libreoffice" / "windows" / "temp"
            extract_dir.mkdir(parents=True, exist_ok=True)

            # Распаковываем MSI
            cmd = ['msiexec', '/a', str(self.msi_path), '/quiet', f'TARGETDIR={extract_dir}']
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=180)

            if result.returncode == 0:
                # Ищем распакованные файлы
                for root, dirs, files in os.walk(extract_dir):
                    if 'soffice.exe' in files:
                        source = Path(root)
                        target = self.base_dir / "libreoffice" / "windows" / "LibreOffice"
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(source, target)
                        shutil.rmtree(extract_dir)
                        return True

            return False
        except Exception as e:
            logger.error(f"Ошибка распаковки MSI: {e}")
            return False

    def is_installed(self) -> bool:
        """Проверяет, доступен ли встроенный LibreOffice"""
        # Для Windows может потребоваться распаковка
        if self.system == 'windows' and not self.bin_path.exists():
            if hasattr(self, 'msi_path') and self.msi_path.exists():
                logger.info("Распаковка MSI...")
                if self.extract_windows():
                    logger.info("MSI распакован успешно")

        if self.bin_path.exists():
            logger.info("Найден встроенный LibreOffice")
            return True

        # Проверяем системную установку как запасной вариант
        if self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                self.bin_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                logger.info("Найден системный LibreOffice")
                return True
        elif self.system == 'windows':
            paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    logger.info("Найден системный LibreOffice")
                    return True
        else:
            # Linux
            if shutil.which('libreoffice'):
                self.bin_path = Path(shutil.which('libreoffice'))
                return True
            if shutil.which('soffice'):
                self.bin_path = Path(shutil.which('soffice'))
                return True

        return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Версия уже встроена, ничего не делаем"""
        return self.is_installed()

    def convert(self, input_path: Path, output_path: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Конвертирует файл через встроенный LibreOffice"""
        if not self.is_installed():
            logger.error("LibreOffice не найден")
            return False

        cmd = [
            str(self.bin_path),
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        logger.info(f"Запуск: {' '.join(cmd)}")

        try:
            if progress_callback:
                progress_callback(50)

            # Для Windows нужен shell=True
            use_shell = self.system == 'windows'
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=use_shell)

            logger.info(f"Код возврата: {result.returncode}")
            if result.stdout:
                logger.info(f"stdout: {result.stdout}")
            if result.stderr:
                logger.info(f"stderr: {result.stderr}")

            if progress_callback:
                progress_callback(80)

            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                return True

            # Ищем PDF в папке
            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    return True

            logger.error(f"PDF не создан")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False