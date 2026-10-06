"""
PDF to Image - конвертирует PDF в изображения (через PyMuPDF).
Одна страница — один файл; несколько — ZIP-архив со страницами.
"""
import io
import zipfile
from pathlib import Path
from typing import List
from PIL import Image
from .base import BaseConverter
from loguru import logger

PIL_FORMATS = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP', 'bmp': 'BMP', 'gif': 'GIF',
               'tiff': 'TIFF'}


class PdfToImageConverter(BaseConverter):
    """Конвертер PDF в изображения"""

    def __init__(self, quality: int = 85, dpi: int = 200):
        super().__init__()
        self.quality = quality
        self.dpi = dpi
        self.page_range = None  # Диапазон страниц, например "1-5,10,15-20"

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return list(PIL_FORMATS)

    def set_quality(self, quality: int):
        """Устанавливает качество для JPEG/WebP"""
        self.quality = max(1, min(100, quality))

    def set_dpi(self, dpi: int):
        """Устанавливает DPI для конвертации"""
        self.dpi = max(72, min(600, dpi))

    def set_page_range(self, page_range: str):
        """Устанавливает диапазон страниц для конвертации"""
        self.page_range = page_range

    def _parse_page_range(self, total_pages: int) -> List[int]:
        """Номера страниц с единицы; диапазон вида '1-5,10,15-20'"""
        if not self.page_range:
            return list(range(1, total_pages + 1))

        pages = set()
        for part in self.page_range.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                pages.update(range(max(1, start), min(total_pages, end) + 1))
            else:
                page_num = int(part)
                if 1 <= page_num <= total_pages:
                    pages.add(page_num)

        return sorted(pages)

    def _save(self, img: Image.Image, target, output_format: str):
        """Сохраняет страницу в файл или в поток."""
        save_kwargs = {}
        if output_format in ('jpg', 'jpeg'):
            save_kwargs = {'quality': self.quality, 'optimize': True}
        elif output_format == 'webp':
            save_kwargs = {'quality': self.quality}
        elif output_format == 'png':
            save_kwargs = {'compress_level': 6}
        elif output_format == 'tiff':
            save_kwargs = {'compression': 'tiff_lzw'}     # без сжатия страница A4 весит ~11 МБ
        img.save(target, PIL_FORMATS[output_format], **save_kwargs)

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            import fitz

            self._update_status("Подготовка к конвертации PDF в изображения...")
            self._update_progress(10)
            output_format = output_path.suffix.lower().lstrip('.')

            with fitz.open(str(input_path)) as doc:
                pages = self._parse_page_range(len(doc))
                if not pages:
                    self._handle_error("Не выбрано ни одной страницы для конвертации")
                    return False

                def render(page_num: int) -> Image.Image:
                    pix = doc[page_num - 1].get_pixmap(dpi=self.dpi, alpha=False)
                    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                if len(pages) == 1:
                    self._save(render(pages[0]), output_path, output_format)
                    self._update_progress(100)
                    self._update_status("Изображение успешно сохранено!")
                    return True

                # Несколько страниц — архив. Рисуем и пишем по одной: 100 страниц при 200 DPI
                # заняли бы в памяти больше гигабайта
                # Свободное имя: лежащий в папке «отчёт.zip» не затираем
                from src.utils.helpers import get_unique_filename
                zip_path = get_unique_filename(output_path.with_suffix('.zip'))
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                    for i, page_num in enumerate(pages):
                        self._update_progress(10 + int(i / len(pages) * 90))
                        self._update_status(f"Страница {page_num} ({i + 1} из {len(pages)})")
                        buffer = io.BytesIO()
                        self._save(render(page_num), buffer, output_format)
                        archive.writestr(f"{output_path.stem}_page_{page_num}.{output_format}", buffer.getvalue())

            self._update_progress(100)
            self._update_status(f"Создан архив: {zip_path.name} ({len(pages)} страниц)")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации PDF в изображения: {str(e)}")
            logger.exception("Ошибка конвертации PDF в изображения")
            return False
