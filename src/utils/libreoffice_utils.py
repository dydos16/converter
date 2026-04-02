"""
Утилиты для работы с LibreOffice
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from loguru import logger


class LibreOfficeUtils:
    """Утилиты для работы с LibreOffice"""

    def __init__(self):
        self.system = platform.system().lower()
        self._soffice_path = None

    def get_soffice_path(self) -> Optional[Path]:
        """Возвращает путь к исполняемому файлу LibreOffice"""
        if self._soffice_path and self._soffice_path.exists():
            return self._soffice_path

        # Проверяем системные пути
        for name in ['libreoffice', 'soffice']:
            path = shutil.which(name)
            if path:
                self._soffice_path = Path(path)
                return self._soffice_path

        # Проверяем встроенную в проект версию
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent.parent / "Resources"
        else:
            base = Path(__file__).parent.parent.parent

        if self.system == 'darwin':  # macOS
            paths = [
                base / "resources" / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            ]
            for path in paths:
                if path.exists():
                    self._soffice_path = path
                    return self._soffice_path

        elif self.system == 'windows':
            paths = [
                base / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe",
                'C:/Program Files/LibreOffice/program/soffice.exe',
            ]
            for path in paths:
                if path.exists():
                    self._soffice_path = path
                    return self._soffice_path

        else:  # linux
            paths = ['/usr/bin/libreoffice', '/usr/bin/soffice']
            for path in paths:
                if path.exists():
                    self._soffice_path = path
                    return self._soffice_path

        return None

    def is_installed(self) -> bool:
        """Проверяет, установлен ли LibreOffice"""
        return self.get_soffice_path() is not None

    def download_and_install(self, progress_callback=None) -> bool:
        """Скачивает и устанавливает LibreOffice автоматически"""
        try:
            if progress_callback:
                progress_callback(10)

            # Импортируем download_libreoffice
            import importlib.util

            if getattr(sys, 'frozen', False):
                base = Path(sys.executable).parent.parent / "Resources"
            else:
                base = Path(__file__).parent.parent.parent

            script_path = base / "download_libreoffice.py"

            if not script_path.exists():
                logger.error(f"download_libreoffice.py не найден: {script_path}")
                return False

            # Загружаем и запускаем скрипт
            spec = importlib.util.spec_from_file_location("download_libreoffice", script_path)
            download_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(download_module)

            if progress_callback:
                progress_callback(50)

            # Запускаем установку
            success = download_module.main()

            if progress_callback:
                progress_callback(100)

            if success:
                # Обновляем путь
                self._soffice_path = None
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка установки LibreOffice: {e}")
            return False

    def get_install_instructions(self) -> str:
        """Возвращает инструкцию по установке"""
        if self.system == 'darwin':
            return "Установите LibreOffice:\nbrew install --cask libreoffice"
        elif self.system == 'windows':
            return "Установите LibreOffice:\nhttps://www.libreoffice.org/download/"
        else:
            return "Установите LibreOffice:\nsudo apt install libreoffice"

    def convert_to_pdf(self, input_path: Path, output_path: Path,
                       progress_callback=None) -> bool:
        """Конвертирует файл в PDF"""
        soffice = self.get_soffice_path()
        if not soffice:
            # Пробуем скачать
            if progress_callback:
                progress_callback(5)
            if self.download_and_install(progress_callback):
                soffice = self.get_soffice_path()
            else:
                return False

        cmd = [
            str(soffice),
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            expected = output_path.parent / f"{input_path.stem}.pdf"
            if expected.exists():
                if expected != output_path:
                    expected.rename(output_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False