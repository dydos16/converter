"""
Единые утилиты для работы с LibreOffice
Убирает копипасту из конвертеров
"""
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger


class LibreOfficeUtils:
    """Единый класс для работы с LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self._soffice_path: Optional[Path] = None
        self._cached_available: Optional[bool] = None

    def find_soffice(self) -> Optional[Path]:
        """Находит путь к исполняемому файлу LibreOffice"""
        if self._soffice_path:
            return self._soffice_path

        # 1. Проверяем в PATH
        for name in ['libreoffice', 'soffice']:
            path = shutil.which(name)
            if path:
                self._soffice_path = Path(path)
                logger.debug(f"LibreOffice найден в PATH: {self._soffice_path}")
                return self._soffice_path

        # 2. Проверяем системные пути
        project_root = Path(__file__).parent.parent.parent

        if self.system == 'darwin':
            paths = [
                project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
                Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                Path('/opt/homebrew/bin/soffice'),  # M1/M2 Mac
                Path('/usr/local/bin/soffice'),     # Intel Mac
            ]
        elif self.system == 'windows':
            paths = [
                project_root / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe",
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]
        else:  # linux
            paths = [
                Path('/usr/bin/libreoffice'),
                Path('/usr/bin/soffice'),
                Path('/snap/bin/libreoffice'),
                Path('/usr/local/bin/libreoffice'),
            ]

        for path in paths:
            if path.exists():
                self._soffice_path = path
                logger.debug(f"LibreOffice найден: {self._soffice_path}")
                return self._soffice_path

        logger.debug("LibreOffice не найден")
        return None

    def is_installed(self) -> bool:
        """Проверяет, установлен ли LibreOffice и работает ли"""
        if self._cached_available is not None:
            return self._cached_available

        soffice = self.find_soffice()
        if not soffice:
            self._cached_available = False
            return False

        try:
            result = subprocess.run(
                [str(soffice), '--version'],
                capture_output=True,
                timeout=10
            )
            self._cached_available = result.returncode == 0

            if self._cached_available:
                version = result.stdout.decode('utf-8', errors='ignore').strip()
                logger.info(f"LibreOffice готов: {version[:50]}")

            return self._cached_available
        except Exception as e:
            logger.warning(f"LibreOffice не отвечает: {e}")
            self._cached_available = False
            return False

    def get_version(self) -> Optional[str]:
        """Возвращает версию LibreOffice"""
        if not self.is_installed():
            return None

        try:
            result = subprocess.run(
                [str(self._soffice_path), '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Ошибка получения версии: {e}")

        return None

    def get_install_instructions(self) -> str:
        """Возвращает инструкцию по установке для текущей ОС"""
        if self.system == 'darwin':
            return (
                "❌ LibreOffice не найден!\n\n"
                "📥 Установите через Homebrew:\n"
                "   brew install --cask libreoffice\n\n"
                "Или скачайте с официального сайта:\n"
                "   https://www.libreoffice.org/download/"
            )
        elif self.system == 'windows':
            return (
                "❌ LibreOffice не найден!\n\n"
                "📥 Скачайте и установите с официального сайта:\n"
                "   https://www.libreoffice.org/download/\n\n"
                "После установки перезапустите приложение."
            )
        else:
            return (
                "❌ LibreOffice не найден!\n\n"
                "📥 Установите через пакетный менеджер:\n"
                "   Ubuntu/Debian: sudo apt install libreoffice\n"
                "   Fedora:        sudo dnf install libreoffice\n"
                "   Arch:          sudo pacman -S libreoffice-fresh"
            )

    def convert_to_pdf(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback=None
    ) -> bool:
        """Конвертирует документ в PDF через LibreOffice"""
        if not self.is_installed():
            logger.error("LibreOffice не найден")
            return False

        cmd = [
            str(self._soffice_path),
            '--headless',
            '--invisible',
            '--nocrashreport',
            '--nofirststartwizard',
            '--nologo',
            '--norestore',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        logger.debug(f"Запуск LibreOffice: {' '.join(cmd)}")

        try:
            if progress_callback:
                progress_callback(50)

            # Скрываем окно на Windows
            startupinfo = None
            if self.system == 'windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                startupinfo=startupinfo
            )

            if progress_callback:
                progress_callback(80)

            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                logger.info(f"PDF создан: {output_path}")
                return True

            # Иногда LibreOffice добавляет суффикс
            for file in output_path.parent.glob(f"{input_path.stem}*.pdf"):
                if file != output_path:
                    file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    logger.info(f"PDF создан (с суффиксом): {output_path}")
                    return True

            logger.error(f"PDF не создан. stderr: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("Таймаут конвертации LibreOffice (300с)")
            return False
        except Exception as e:
            logger.exception(f"Ошибка конвертации LibreOffice: {e}")
            return False

    def convert_to_format(
        self,
        input_path: Path,
        output_path: Path,
        target_format: str,
        progress_callback=None
    ) -> bool:
        """Конвертирует в произвольный формат через LibreOffice"""
        if not self.is_installed():
            logger.error("LibreOffice не найден")
            return False

        cmd = [
            str(self._soffice_path),
            '--headless',
            '--invisible',
            '--nocrashreport',
            '--nofirststartwizard',
            '--nologo',
            '--norestore',
            '--convert-to', target_format,
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        logger.debug(f"Запуск LibreOffice (->{target_format}): {' '.join(cmd)}")

        try:
            if progress_callback:
                progress_callback(50)

            startupinfo = None
            if self.system == 'windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                startupinfo=startupinfo
            )

            expected_file = output_path.parent / f"{input_path.stem}.{target_format}"
            if expected_file.exists():
                if expected_file != output_path:
                    expected_file.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                logger.info(f"Файл создан: {output_path}")
                return True

            # Ищем с суффиксом
            for file in output_path.parent.glob(f"{input_path.stem}*.{target_format}"):
                if file != output_path:
                    file.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    logger.info(f"Файл создан (с суффиксом): {output_path}")
                    return True

            logger.error(f"Файл не создан. stderr: {result.stderr}")
            return False

        except Exception as e:
            logger.exception(f"Ошибка конвертации: {e}")
            return False