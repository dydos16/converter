"""
PDF to PPTX - конвертация PDF в презентацию PowerPoint через преобразование в изображения
"""
import tempfile
from pathlib import Path
from .base import BaseConverter
from loguru import logger

EMU_PER_PT = 12700                  # единицы PowerPoint в одном типографском пункте
MAX_SLIDE_PT = 56 * 72              # PowerPoint не принимает слайды больше 56 дюймов


class PdfToPptxConverter(BaseConverter):
    """Конвертер PDF в PPTX: каждая страница — картинка на своём слайде"""

    def __init__(self):
        super().__init__()
        self.dpi = 150
        self.quality = 85

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['pptx', 'ppt', 'odp']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        # ppt/odp писать сами не умеем: делаем PPTX и пересохраняем через LibreOffice
        if output_path.suffix.lower() != '.pptx':
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager().convert_via(lambda pptx: self.convert(input_path, pptx), output_path, '.pptx')
        try:
            # Страницы рисует PyMuPDF — он уже в приложении, внешний poppler не нужен
            import fitz
            from pptx import Presentation

            self._update_status(f"Конвертация PDF в изображения (DPI={self.dpi})...")
            self._update_progress(10)

            with fitz.open(input_path) as doc, tempfile.TemporaryDirectory() as tmp:
                total_pages = len(doc)
                prs = Presentation()
                # Слайд — по пропорциям первой страницы, иначе A4 растягивается в 16:9
                first = doc[0].rect
                k = min(1.0, MAX_SLIDE_PT / max(first.width, first.height))
                prs.slide_width = int(first.width * k * EMU_PER_PT)
                prs.slide_height = int(first.height * k * EMU_PER_PT)

                for i, page in enumerate(doc):
                    self._update_progress(10 + int(i / total_pages * 85))
                    self._update_status(f"Слайд {i + 1}/{total_pages}")
                    png = Path(tmp) / f"{i}.png"
                    page.get_pixmap(dpi=self.dpi).save(png)
                    # Страница целиком и без искажений: вписываем по центру, сохраняя пропорции
                    scale = min(prs.slide_width / page.rect.width, prs.slide_height / page.rect.height)
                    w, h = int(page.rect.width * scale), int(page.rect.height * scale)
                    slide = prs.slides.add_slide(prs.slide_layouts[6])
                    slide.shapes.add_picture(str(png), (prs.slide_width - w) // 2, (prs.slide_height - h) // 2, w, h)

                self._update_status("Сохранение презентации...")
                self._update_progress(95)
                prs.save(str(output_path))

            self._update_progress(100)
            self._update_status(f"Конвертация завершена! Создано {total_pages} слайдов")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в PPTX")
            return False
