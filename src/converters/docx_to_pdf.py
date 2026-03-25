"""
DOCX to PDF - через python-docx2pdf
"""
from pathlib import Path
import sys
import shutil
from docx2pdf import convert
from .base import BaseConverter
from loguru import logger


class DocxToPdfConverter(BaseConverter):

    def get_input_formats(self):
        return ['docx', 'doc']

    def get_output_formats(self):
        return ['pdf']

    def check_libreoffice(self):
        """Проверяет наличие LibreOffice"""
        paths = []

        if sys.platform == 'darwin':  # macOS
            paths = [
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
                '/Applications/LibreOffice.app/Contents/MacOS/libreoffice',
            ]
        elif sys.platform == 'win32':  # Windows
            paths = [
                r'C:\Program Files\LibreOffice\program\soffice.exe',
                r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
            ]
        else:  # Linux
            paths = [
                '/usr/bin/libreoffice',
                '/usr/bin/soffice',
                '/opt/libreoffice/program/soffice',
            ]

        # Проверяем пути
        for path in paths:
            if Path(path).exists():
                logger.info(f"LibreOffice найден: {path}")
                return True

        # Проверяем в PATH
        if shutil.which('soffice') or shutil.which('libreoffice'):
            logger.info("LibreOffice найден в PATH")
            return True

        logger.warning("LibreOffice не найден!")
        return False

    def get_install_instructions(self):
        """Возвращает инструкцию по установке LibreOffice"""
        if sys.platform == 'darwin':
            return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Способы установки:

1. Через Homebrew (рекомендуется):
   brew install --cask libreoffice

2. Скачать с официального сайта:
   https://www.libreoffice.org/download/

После установки перезапустите приложение.
            """
        elif sys.platform == 'win32':
            return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Скачайте установщик с официального сайта:
   https://www.libreoffice.org/download/

После установки перезапустите приложение.
            """
        else:
            return """
LibreOffice не найден. Для конвертации DOCX в PDF необходимо установить LibreOffice.

Способы установки:

Ubuntu/Debian:
   sudo apt update
   sudo apt install libreoffice

CentOS/RHEL:
   sudo yum install libreoffice

Arch Linux:
   sudo pacman -S libreoffice-fresh

После установки перезапустите приложение.
            """

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка зависимостей...")
            self._update_progress(20)

            # Проверяем наличие LibreOffice
            if not self.check_libreoffice():
                error_msg = self.get_install_instructions()
                self._handle_error(error_msg)
                return False

            self._update_status("Конвертация DOCX в PDF...")
            self._update_progress(50)

            # Конвертируем
            convert(str(input_path), str(output_path))

            # Проверяем, создался ли файл
            if output_path.exists() and output_path.stat().st_size > 0:
                self._update_progress(100)
                self._update_status("Конвертация завершена!")
                logger.success(f"PDF создан: {output_path}")
                return True
            else:
                self._handle_error("PDF файл не был создан")
                return False

        except Exception as e:
            error_msg = str(e)
            if "No such file" in error_msg:
                error_msg = "Не удалось найти LibreOffice. " + self.get_install_instructions()
            self._handle_error(error_msg)
            logger.exception("Ошибка конвертации")
            return False