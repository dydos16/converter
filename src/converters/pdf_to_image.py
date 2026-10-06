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
# Потолок на страницу — 100 Мпикс (A0 — около 254 DPI, A4 при 600 DPI — 35 Мпикс, не задевает).
# Чертёж A0 при 600 DPI — 557 Мпикс: 3,7 ГБ памяти и падение на обычном ноутбуке
MAX_PAGE_PIXELS = 100_000_000


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

    def _render(self, page) -> bytes:
        """Страница → готовый файл картинки (байты). DPI снижаем, если страница вышла бы больше MAX_PAGE_PIXELS."""
        dpi = self.dpi
        w, h = page.rect.width / 72 * dpi, page.rect.height / 72 * dpi
        scale = min(1.0, (MAX_PAGE_PIXELS / (w * h)) ** 0.5)
        if self._format == 'webp':
            scale = min(scale, 16383 / max(w, h))           # больше по стороне WebP не умеет
        if scale < 1:
            dpi = int(dpi * scale)
            self._update_status(f"Страница очень большая — рисуем с {dpi} DPI вместо {self.dpi}")
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        # PNG и JPEG кодирует сам PyMuPDF: копия страницы в Pillow удвоила бы память
        if self._format == 'png':
            return pix.tobytes("png")
        if self._format in ('jpg', 'jpeg'):
            return pix.tobytes("jpeg", jpg_quality=self.quality)
        save_kwargs = {}
        if self._format == 'webp':
            save_kwargs = {'quality': self.quality}
        elif self._format == 'tiff':
            save_kwargs = {'compression': 'tiff_lzw'}     # без сжатия страница A4 весит ~11 МБ
        buffer = io.BytesIO()
        Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(buffer, PIL_FORMATS[self._format], **save_kwargs)
        return buffer.getvalue()

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            import fitz

            self._update_status("Подготовка к конвертации PDF в изображения...")
            self._update_progress(10)
            output_format = self._format = output_path.suffix.lower().lstrip('.')

            with fitz.open(str(input_path)) as doc:
                pages = self._parse_page_range(len(doc))
                if not pages:
                    self._handle_error("Не выбрано ни одной страницы для конвертации")
                    return False

                if len(pages) == 1:
                    output_path.write_bytes(self._render(doc[pages[0] - 1]))
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
                        archive.writestr(f"{output_path.stem}_page_{page_num}.{output_format}",
                                         self._render(doc[page_num - 1]))

            self._update_progress(100)
            self._update_status(f"Создан архив: {zip_path.name} ({len(pages)} страниц)")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации PDF в изображения: {str(e)}")
            logger.exception("Ошибка конвертации PDF в изображения")
            return False
