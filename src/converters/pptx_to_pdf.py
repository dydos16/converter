"""
PowerPoint to PDF - через LibreOffice
Поддерживает: .pptx, .ppt, .pps, .ppsx
"""
from pathlib import Path
import sys
import shutil
import subprocess
from .base import BaseConverter
from loguru import logger


class PptxToPdfConverter(BaseConverter):

    def get_input_formats(self):
        return ['pptx', 'ppt', 'pps', 'ppsx']

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

    def get_install_instructions(self):
        """Инструкция по установке"""
        if sys.platform == 'darwin':
            return """
LibreOffice не найден. Для конвертации PowerPoint файлов в PDF необходимо установить LibreOffice.

Установите через Homebrew:
  brew install --cask libreoffice

Или скачайте с официального сайта:
  https://www.libreoffice.org/download/

После установки перезапустите приложение.
            """
        elif sys.platform == 'win32':
            return """
LibreOffice не найден. Для конвертации PowerPoint файлов в PDF необходимо установить LibreOffice.

Скачайте установщик с официального сайта:
  https://www.libreoffice.org/download/

После установки перезапустите приложение.
            """
        else:
            return """
LibreOffice не найден. Для конвертации PowerPoint файлов в PDF необходимо установить LibreOffice.

Установите через пакетный менеджер:
  sudo apt install libreoffice     (Ubuntu/Debian)
  sudo yum install libreoffice     (CentOS/RHEL)
  sudo pacman -S libreoffice-fresh (Arch)

После установки перезапустите приложение.
            """

    def find_soffice(self):
        """Находит путь к soffice"""
        paths = []

        if sys.platform == 'darwin':  # macOS
            paths = [
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
                '/Applications/LibreOffice.app/Contents/MacOS/libreoffice',
                '/usr/local/bin/soffice',
            ]
        elif sys.platform == 'win32':  # Windows
            paths = [
                r'C:\Program Files\LibreOffice\program\soffice.exe',
                r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
                r'C:\Program Files\LibreOffice\program\soffice.bin',
            ]
        else:  # Linux
            paths = [
                '/usr/bin/libreoffice',
                '/usr/bin/soffice',
                '/opt/libreoffice/program/soffice',
                '/opt/libreoffice7.6/program/soffice',
            ]

        for path in paths:
            if Path(path).exists():
                return path

        # Проверяем в PATH
        soffice = shutil.which('soffice') or shutil.which('libreoffice')
        if soffice:
            return soffice

        return None

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            ext = input_path.suffix.lower()

            self._update_status("Проверка зависимостей...")
            self._update_progress(20)

            # Проверяем LibreOffice
            if not self.check_libreoffice():
                self._handle_error(self.get_install_instructions())
                return False

            self._update_status(f"Конвертация {ext} в PDF...")
            self._update_progress(50)

            # Находим soffice
            soffice_path = self.find_soffice()

            if not soffice_path:
                self._handle_error("Не удалось найти LibreOffice")
                return False

            # Запускаем конвертацию
            cmd = [
                str(soffice_path),
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_path.parent),
                str(input_path)
            ]

            logger.info(f"Запуск: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Проверяем результат
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"

            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)

                if output_path.exists() and output_path.stat().st_size > 0:
                    self._update_progress(100)
                    self._update_status("Готово!")
                    logger.success(f"PDF создан: {output_path}")
                    return True
                else:
                    self._handle_error("PDF файл поврежден")
                    return False
            else:
                # Пробуем найти PDF с другим именем
                for pdf_file in output_path.parent.glob("*.pdf"):
                    if pdf_file.stat().st_size > 0:
                        pdf_file.rename(output_path)
                        self._update_progress(100)
                        self._update_status("Готово!")
                        return True

                error_msg = result.stderr if result.stderr else "PDF не создан"
                self._handle_error(f"Ошибка конвертации: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self._handle_error("Превышено время ожидания конвертации (5 минут)")
            return False
        except Exception as e:
            self._handle_error(str(e))
            logger.exception("Ошибка конвертации")
            return False