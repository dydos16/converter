"""
Менеджер для использования встроенной версии LibreOffice
"""
import sys
import os
import platform
import subprocess
import shutil
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
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            base = Path(__file__).parent.parent.parent
            self.base_dir = base / "resources"

        if self.system == 'darwin':
            self.bin_path = self.base_dir / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
        elif self.system == 'windows':
            self.msi_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice_26.2.2_Win_x86-64.msi"
            self.bin_path = self.base_dir / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe"
        else:  # Linux
            self.bin_path = Path("/usr/bin/libreoffice")

    def is_installed(self) -> bool:
        """Проверяет, доступен ли LibreOffice"""
        import shutil

        # 1. Проверяем системную версию (приоритет)
        if shutil.which('libreoffice'):
            self.bin_path = Path(shutil.which('libreoffice'))
            logger.info(f"Найден системный LibreOffice: {self.bin_path}")
            return True

        if shutil.which('soffice'):
            self.bin_path = Path(shutil.which('soffice'))
            logger.info(f"Найден системный LibreOffice: {self.bin_path}")
            return True

        # 2. Для macOS проверяем Applications
        if self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                self.bin_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                logger.info("Найден системный LibreOffice в Applications")
                return True

        # 3. Для Windows проверяем Program Files
        if self.system == 'windows':
            paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
            for path in paths:
                if path.exists():
                    self.bin_path = path
                    logger.info(f"Найден системный LibreOffice: {self.bin_path}")
                    return True

        # 4. Проверяем встроенную версию
        if self.bin_path.exists():
            logger.info(f"Найден встроенный LibreOffice: {self.bin_path}")
            return True

        logger.warning("LibreOffice не найден")
        return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Версия уже встроена, ничего не делаем"""
        return self.is_installed()

    def convert(self, input_path: Path, output_path: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Конвертирует файл через LibreOffice"""
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