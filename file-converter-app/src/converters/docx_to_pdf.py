"""
Конвертер DOCX в PDF с использованием LibreOffice
"""
import subprocess
import sys
from pathlib import Path
from .base import BaseConverter
from src.utils.helpers import find_libreoffice, create_temp_dir, cleanup_temp_dir
from loguru import logger


class DocxToPdfConverter(BaseConverter):
    """Конвертер DOCX и DOC в PDF"""

    def __init__(self):
        super().__init__()
        self.libreoffice_path = find_libreoffice()

    def get_input_formats(self) -> list[str]:
        return ['docx', 'doc']

    def get_output_formats(self) -> list[str]:
        return ['pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        """
        Конвертирует DOCX/DOC в PDF используя LibreOffice

        Использует headless режим LibreOffice для максимальной совместимости
        с форматированием документов
        """
        if not self.libreoffice_path:
            self._handle_error("LibreOffice не найден. Пожалуйста, установите LibreOffice")
            return False

        temp_dir = None

        try:
            self._update_status("Подготовка к конвертации...")
            self._update_progress(10)

            # Создаем временную директорию для конвертации
            temp_dir = create_temp_dir()

            # Команда для LibreOffice
            cmd = [
                str(self.libreoffice_path),
                '--headless',  # Без графического интерфейса
                '--convert-to', 'pdf',
                '--outdir', str(temp_dir),
                str(input_path)
            ]

            self._update_status(f"Запуск LibreOffice: {' '.join(cmd)}")
            logger.info(f"Запуск конвертации: {' '.join(cmd)}")
            self._update_progress(30)

            # Запускаем процесс
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )

            self._update_status("Конвертация в процессе...")
            self._update_progress(50)

            # Ждем завершения
            stdout, stderr = process.communicate(timeout=300)  # 5 минут таймаут

            if process.returncode != 0:
                self._handle_error(f"Ошибка LibreOffice: {stderr}")
                return False

            self._update_progress(80)

            # LibreOffice создает файл в temp_dir с именем как у исходного
            generated_pdf = temp_dir / f"{input_path.stem}.pdf"

            if not generated_pdf.exists():
                self._handle_error("PDF файл не был создан")
                return False

            # Перемещаем в нужное место
            generated_pdf.rename(output_path)

            self._update_progress(100)
            self._update_status("Конвертация завершена!")

            return True

        except subprocess.TimeoutExpired:
            self._handle_error("Превышено время ожидания конвертации")
            process.kill()
            return False

        except Exception as e:
            self._handle_error(f"Ошибка при конвертации: {str(e)}")
            return False

        finally:
            # Очищаем временные файлы
            if temp_dir:
                cleanup_temp_dir(temp_dir)