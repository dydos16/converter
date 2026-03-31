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
        # Определяем корневую директорию проекта
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
            if self.system == 'darwin':
                self.base_dir = base.parent / "Resources"
            else:
                self.base_dir = base
        else:
            base = Path(__file__).parent.parent.parent
            self.base_dir = base / "resources"

        # Пути для разных ОС
        if self.system == 'darwin':
            # macOS
            self.bin_path = self.base_dir / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"

        elif self.system == 'windows':
            # Windows - возможные пути
            self.possible_paths = [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
                self.base_dir / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe",
                self.base_dir / "libreoffice" / "windows" / "extract" / "PFiles" / "LibreOffice" / "program" / "soffice.exe",
                self.base_dir / "libreoffice" / "windows" / "resources" / "libreoffice" / "windows" / "extract" / "PFiles" / "LibreOffice" / "program" / "soffice.exe",
            ]
            self.bin_path = self.possible_paths[0]

        else:  # Linux
            self.bin_path = Path("/usr/bin/libreoffice")

        logger.info(f"Путь к LibreOffice: {self.bin_path}")

    def is_installed(self) -> bool:
        """Проверяет, доступен ли LibreOffice"""
        # 1. Проверяем системную версию (приоритет)
        if self.system == 'windows':
            for path in self.possible_paths:
                if path.exists():
                    self.bin_path = path
                    logger.info(f"Найден LibreOffice: {self.bin_path}")
                    return True

        elif self.system == 'linux':
            if shutil.which('libreoffice'):
                self.bin_path = Path(shutil.which('libreoffice'))
                logger.info(f"Найден системный LibreOffice: {self.bin_path}")
                return True
            if shutil.which('soffice'):
                self.bin_path = Path(shutil.which('soffice'))
                logger.info(f"Найден системный LibreOffice: {self.bin_path}")
                return True

        elif self.system == 'darwin':
            if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists():
                self.bin_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                logger.info("Найден системный LibreOffice в Applications")
                return True

        # 2. Проверяем встроенную в проект версию
        if self.bin_path.exists():
            logger.info(f"Найден встроенный LibreOffice: {self.bin_path}")
            return True

        logger.warning("LibreOffice не найден")
        return False

    def install(self, progress_callback: Optional[Callable] = None) -> bool:
        """Установка LibreOffice (если нужно)"""
        if self.is_installed():
            logger.info("LibreOffice уже установлен")
            return True

        # Показываем инструкцию по установке
        if self.system == 'darwin':
            print("\n" + "="*60)
            print("  Установка LibreOffice для macOS")
            print("="*60)
            print("\nУстановите LibreOffice через Homebrew:")
            print("  brew install --cask libreoffice")
            print("\nИли скачайте с официального сайта:")
            print("  https://www.libreoffice.org/download/")
            print("\nПосле установки перезапустите приложение.")

        elif self.system == 'windows':
            print("\n" + "="*60)
            print("  Установка LibreOffice для Windows")
            print("="*60)
            print("\nСкачайте установщик с официального сайта:")
            print("  https://www.libreoffice.org/download/")
            print("\nЗапустите скачанный файл и следуйте инструкциям.")
            print("\nПосле установки перезапустите приложение.")

        else:
            print("\n" + "="*60)
            print("  Установка LibreOffice для Linux")
            print("="*60)
            print("\nУстановите через пакетный менеджер:")
            print("  sudo apt update && sudo apt install -y libreoffice")
            print("\nИли:")
            print("  sudo dnf install libreoffice")
            print("  sudo pacman -S libreoffice-fresh")
            print("\nПосле установки перезапустите приложение.")

        return False

    def convert(self, input_path: Path, output_path: Path, progress_callback: Optional[Callable] = None) -> bool:
        """Конвертирует файл через LibreOffice"""
        if not self.is_installed():
            logger.error("LibreOffice не найден")
            return False

        # Убедимся, что bin_path существует
        if not self.bin_path.exists():
            logger.error(f"LibreOffice не найден по пути: {self.bin_path}")
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
            use_shell = (self.system == 'windows')
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                shell=use_shell
            )

            logger.info(f"Код возврата: {result.returncode}")
            if result.stdout:
                logger.info(f"stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.info(f"stderr: {result.stderr[:500]}")

            if progress_callback:
                progress_callback(80)

            # Ищем созданный PDF
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                logger.success(f"PDF создан: {output_path}")
                return True

            # Ищем PDF в папке
            for pdf_file in output_path.parent.glob("*.pdf"):
                if pdf_file.stat().st_size > 0:
                    pdf_file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    logger.success(f"PDF создан: {output_path}")
                    return True

            logger.error(f"PDF не создан. stderr: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Превышено время конвертации (5 минут)")
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False