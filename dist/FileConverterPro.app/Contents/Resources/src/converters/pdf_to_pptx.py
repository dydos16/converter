"""
PDF to PPTX - конвертация PDF в презентацию PowerPoint через преобразование в изображения
"""
import subprocess
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from .base import BaseConverter
from loguru import logger


class PdfToPptxConverter(BaseConverter):
    """Конвертер PDF в PPTX через преобразование страниц в изображения"""

    def __init__(self):
        super().__init__()
        self.dpi = 150
        self.quality = 85

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['pptx', 'ppt']

    def _check_pdf2image(self):
        try:
            from pdf2image import convert_from_path
            return True
        except ImportError:
            return False

    def _check_python_pptx(self):
        try:
            from pptx import Presentation
            return True
        except ImportError:
            return False

    def _check_poppler(self):
        import shutil
        import platform

        system = platform.system().lower()

        if system == 'darwin':
            return shutil.which('pdfinfo') is not None
        elif system == 'windows':
            return shutil.which('pdftoppm') is not None
        else:
            return shutil.which('pdfinfo') is not None

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Проверка зависимостей...")
            self._update_progress(10)

            # Проверяем poppler
            if not self._check_poppler():
                error_msg = (
                    "Для конвертации PDF в PPTX необходимо установить poppler:\n\n"
                    "- macOS: brew install poppler\n"
                    "- Windows: скачайте poppler и добавьте в PATH\n"
                    "  https://github.com/oschwartz10612/poppler-windows/releases/\n"
                    "- Linux: sudo apt-get install poppler-utils"
                )
                self._handle_error(error_msg)
                return False

            # Проверяем pdf2image
            if not self._check_pdf2image():
                self._handle_error("Установите pdf2image: pip install pdf2image")
                return False

            # Проверяем python-pptx
            if not self._check_python_pptx():
                self._handle_error("Установите python-pptx: pip install python-pptx")
                return False

            from pdf2image import convert_from_path
            from pptx import Presentation
            from pptx.util import Inches

            self._update_status(f"Конвертация PDF в изображения (DPI={self.dpi})...")
            self._update_progress(20)

            # Конвертируем PDF в изображения
            images = convert_from_path(
                str(input_path),
                dpi=self.dpi,
                fmt='png'
            )

            total_pages = len(images)
            self._update_status(f"Создание презентации с {total_pages} слайдами...")
            self._update_progress(40)

            # Создаем презентацию
            prs = Presentation()
            prs.slide_width = Inches(10)
            prs.slide_height = Inches(5.625)

            for i, img in enumerate(images):
                # Обновляем прогресс каждые 10% или каждую страницу
                progress = 40 + int((i / total_pages) * 55)
                self._update_progress(progress)
                self._update_status(f"Слайд {i+1}/{total_pages}")

                # Добавляем слайд
                slide_layout = prs.slide_layouts[6]
                slide = prs.slides.add_slide(slide_layout)

                # Сохраняем изображение во временный файл
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img.save(tmp.name, 'PNG')
                    tmp_path = tmp.name

                # Добавляем изображение на слайд
                slide.shapes.add_picture(
                    tmp_path,
                    Inches(0),
                    Inches(0),
                    width=prs.slide_width,
                    height=prs.slide_height
                )

                # Удаляем временный файл
                Path(tmp_path).unlink()

            # Сохраняем презентацию
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