"""
DOCX to PDF - через LibreOffice
"""
from pathlib import Path
import sys
import shutil
import subprocess
import time
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

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка LibreOffice...")
            self._update_progress(20)

            # Проверяем наличие LibreOffice
            if not self.lo_manager.is_installed():
                self._update_status("LibreOffice не найден. Установка...")
                self._update_progress(30)
                if not self.lo_manager.install():
                    self._handle_error("Не удалось установить LibreOffice")
                    return False

            # Получаем путь к soffice
            soffice_path = self.lo_manager.bin_path
            if not soffice_path.exists():
                # Ищем в системе
                if sys.platform == 'darwin':
                    soffice_path = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
                elif sys.platform == 'win32':
                    paths = [
                        Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                        Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
                    ]
                    for path in paths:
                        if path.exists():
                            soffice_path = path
                            break
                else:
                    which_soffice = shutil.which('libreoffice') or shutil.which('soffice')
                    if which_soffice:
                        soffice_path = Path(which_soffice)

            if not soffice_path.exists():
                self._handle_error(f"LibreOffice не найден: {soffice_path}")
                return False

            self._update_status(f"Конвертация {input_path.name} в PDF...")
            self._update_progress(50)

            # Абсолютные пути
            abs_input = input_path.absolute()
            abs_output = output_path.absolute()

            # Команда
            cmd = [
                str(soffice_path),
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(abs_output.parent),
                str(abs_input)
            ]

            logger.info(f"Запуск: {' '.join(cmd)}")

            # Для Windows нужен shell=True
            use_shell = sys.platform == 'win32'

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                shell=use_shell
            )

            logger.info(f"Код возврата: {result.returncode}")
            if result.stdout:
                logger.info(f"stdout: {result.stdout}")
            if result.stderr:
                logger.info(f"stderr: {result.stderr}")

            self._update_progress(80)

            # Ждём
            time.sleep(1)

            # Ищем PDF
            expected_pdf = abs_output.parent / f"{abs_input.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != abs_output:
                    expected_pdf.rename(abs_output)
                self._update_progress(100)
                self._update_status("Готово!")
                logger.success(f"PDF создан: {abs_output}")
                return True

            # Ищем все PDF
            for pdf in abs_output.parent.glob("*.pdf"):
                if pdf.stat().st_size > 0:
                    if pdf != abs_output:
                        pdf.rename(abs_output)
                    self._update_progress(100)
                    self._update_status("Готово!")
                    logger.success(f"PDF создан: {abs_output}")
                    return True

            self._handle_error(f"PDF не создан. stderr: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            self._handle_error("Превышено время конвертации")
            return False
        except Exception as e:
            self._handle_error(str(e))
            logger.exception("Ошибка конвертации")
            return False