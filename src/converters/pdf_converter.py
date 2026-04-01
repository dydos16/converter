"""
PDF to PDF - оптимизация, сжатие и обработка PDF
"""
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfConverter(BaseConverter):
    """Конвертер для обработки PDF (оптимизация, сжатие)"""

    def __init__(self):
        super().__init__()
        self.compress_level = 0  # 0 - без сжатия, 9 - максимальное сжатие
        self.remove_metadata = False
        self.linearize = False  # Оптимизация для веб-просмотра

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['pdf']

    def set_compress_level(self, level: int):
        """Устанавливает уровень сжатия (0-9)"""
        self.compress_level = max(0, min(9, level))

    def set_remove_metadata(self, remove: bool):
        """Устанавливает удаление метаданных"""
        self.remove_metadata = remove

    def set_linearize(self, linearize: bool):
        """Устанавливает оптимизацию для веб-просмотра"""
        self.linearize = linearize

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Оптимизация PDF...")
            self._update_progress(10)

            # Пробуем использовать PyMuPDF
            try:
                import fitz

                self._update_status("Используем PyMuPDF для оптимизации...")
                self._update_progress(30)

                doc = fitz.open(str(input_path))

                if self.compress_level > 0:
                    self._update_status(f"Сжатие PDF (уровень {self.compress_level})...")
                    self._update_progress(50)

                    # Сохраняем с сжатием
                    doc.save(
                        str(output_path),
                        garbage=self.compress_level,
                        clean=True,
                        deflate=True,
                        deflate_images=True,
                        deflate_fonts=True
                    )
                else:
                    # Просто копируем
                    doc.save(str(output_path))

                if self.remove_metadata:
                    self._update_status("Удаление метаданных...")
                    doc.set_metadata({})
                    doc.save(str(output_path))

                doc.close()

                self._update_progress(100)
                self._update_status("PDF успешно оптимизирован!")

                return True

            except ImportError:
                # Если PyMuPDF нет, используем pypdf
                try:
                    from pypdf import PdfReader, PdfWriter

                    self._update_status("Используем PyPDF для оптимизации...")
                    self._update_progress(30)

                    reader = PdfReader(str(input_path))
                    writer = PdfWriter()

                    total_pages = len(reader.pages)

                    for i, page in enumerate(reader.pages):
                        self._update_progress(30 + int((i / total_pages) * 50))
                        writer.add_page(page)

                    if self.compress_level > 0:
                        # В PyPDF сжатие через compress_content
                        for page in writer.pages:
                            page.compress_content_streams()

                    if self.remove_metadata:
                        writer.add_metadata({})

                    with open(output_path, 'wb') as f:
                        writer.write(f)

                    self._update_progress(100)
                    self._update_status("PDF успешно оптимизирован!")

                    return True

                except ImportError:
                    self._handle_error("Для оптимизации PDF установите PyMuPDF: pip install PyMuPDF")
                    return False

        except Exception as e:
            self._handle_error(f"Ошибка оптимизации PDF: {str(e)}")
            logger.exception("Ошибка оптимизации PDF")
            return False