"""
DOCX to PDF - с автоматической установкой LibreOffice
Поддерживает: .docx, .doc
"""
from pathlib import Path
import sys
import shutil
import subprocess
from .base import BaseConverter
from src.core.libreoffice_manager import LibreOfficeManager
from loguru import logger


class DocxToPdfConverter(BaseConverter):

    def __init__(self):
        super().__init__()
        self.lo_manager = LibreOfficeManager()

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

        for path in paths:
            if Path(path).exists():
                logger.info(f"LibreOffice найден: {path}")
                return True

        if shutil.which('soffice') or shutil.which('libreoffice'):
            logger.info("LibreOffice найден в PATH")
            return True

        return False

    def convert_docx_with_docx2pdf(self, input_path, output_path):
        """Конвертация DOCX через docx2pdf"""
        try:
            from docx2pdf import convert
            convert(str(input_path), str(output_path))
            return True
        except ImportError:
            return False

    def convert_with_libreoffice(self, input_path, output_path):
        """Конвертация через LibreOffice напрямую"""
        soffice_path = None

        # Ищем soffice
        paths = [
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            '/usr/bin/soffice',
            '/usr/bin/libreoffice',
        ]

        if sys.platform == 'win32':
            paths = [
                r'C:\Program Files\LibreOffice\program\soffice.exe',
                r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
            ]

        for path in paths:
            if Path(path).exists():
                soffice_path = path
                break

        if not soffice_path:
            soffice_path = shutil.which('soffice') or shutil.which('libreoffice')

        if not soffice_path:
            return False

        # Запускаем конвертацию
        cmd = [
            str(soffice_path),
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Проверяем результат
        expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
        if expected_pdf.exists() and expected_pdf != output_path:
            expected_pdf.rename(output_path)

        return result.returncode == 0 or output_path.exists()

    def get_install_instructions(self):
        """Инструкция по установке"""
        if sys.platform == 'darwin':
            return """
LibreOffice не найден. Для конвертации DOC/DOCX в PDF необходимо установить LibreOffice.

Установите через Homebrew:
  brew install --cask libreoffice

Или скачайте с официального сайта:
  https://www.libreoffice.org/download/
            """
        elif sys.platform == 'win32':
            return """
LibreOffice не найден. Для конвертации DOC/DOCX в PDF необходимо установить LibreOffice.

Скачайте установщик с официального сайта:
  https://www.libreoffice.org/download/
            """
        else:
            return """
LibreOffice не найден. Для конвертации DOC/DOCX в PDF необходимо установить LibreOffice.

Установите через пакетный менеджер:
  sudo apt install libreoffice     (Ubuntu/Debian)
  sudo yum install libreoffice     (CentOS/RHEL)
  sudo pacman -S libreoffice-fresh (Arch)
            """

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка зависимостей...")
            self._update_progress(10)

            # Проверяем наличие LibreOffice
            if not self.check_libreoffice():
                # Пробуем использовать встроенный менеджер для автоматической установки
                self._update_status("LibreOffice не найден. Начинается автоматическая установка...")
                self._update_progress(20)

                def progress_callback(progress: int):
                    p = 20 + int(progress * 0.4)
                    self._update_progress(p)
                    self._update_status(f"Установка LibreOffice: {progress}%")

                if not self.lo_manager.install(progress_callback):
                    self._handle_error(self.get_install_instructions())
                    return False

                self._update_status("LibreOffice успешно установлен!")
                self._update_progress(60)
            else:
                self._update_status("LibreOffice найден")
                self._update_progress(60)

            ext = input_path.suffix.lower()
            self._update_status(f"Конвертация {ext} в PDF...")
            self._update_progress(65)

            success = False

            # Пробуем docx2pdf для DOCX
            if ext == '.docx':
                try:
                    from docx2pdf import convert
                    convert(str(input_path), str(output_path))
                    success = output_path.exists()
                except:
                    success = self.convert_with_libreoffice(input_path, output_path)

            # Для DOC используем LibreOffice напрямую
            elif ext == '.doc':
                success = self.convert_with_libreoffice(input_path, output_path)

            if success and output_path.exists() and output_path.stat().st_size > 0:
                self._update_progress(100)
                self._update_status("Готово!")
                logger.success(f"PDF создан: {output_path}")
                return True
            else:
                self._handle_error("Не удалось создать PDF")
                return False

        except Exception as e:
            self._handle_error(str(e))
            logger.exception("Ошибка конвертации")
            return False