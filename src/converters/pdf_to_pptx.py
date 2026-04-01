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
        return ['pptx']

    def _check_pdf2image(self):
        """Проверяет доступность pdf2image"""
        try:
            from pdf2image import convert_from_path
            return True
        except ImportError:
            return False

    def _install_pdf2image(self):
        """Устанавливает pdf2image"""
        try:
            import subprocess
            import sys
            self._update_status("Установка pdf2image...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'pdf2image', '--quiet'
            ])
            return True
        except Exception as e:
            logger.error(f"Ошибка установки pdf2image: {e}")
            return False

    def _check_python_pptx(self):
        """Проверяет доступность python-pptx"""
        try:
            from pptx import Presentation
            return True
        except ImportError:
            return False

    def _install_python_pptx(self):
        """Устанавливает python-pptx"""
        try:
            import subprocess
            import sys
            self._update_status("Установка python-pptx...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'python-pptx', '--quiet'
            ])
            return True
        except Exception as e:
            logger.error(f"Ошибка установки python-pptx: {e}")
            return False

    def _check_poppler(self):
        """Проверяет наличие poppler (для pdf2image)"""
        import shutil
        import platform

        system = platform.system().lower()

        if system == 'darwin':
            return shutil.which('pdfinfo') is not None
        elif system == 'windows':
            # На Windows poppler должен быть в PATH
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
                    "- Linux: sudo apt-get install poppler-utils\n\n"
                    "После установки перезапустите приложение"
                )
                self._handle_error(error_msg)
                return False

            # Проверяем pdf2image
            if not self._check_pdf2image():
                if not self._install_pdf2image():
                    self._handle_error("Не удалось установить pdf2image")
                    return False

            # Проверяем python-pptx
            if not self._check_python_pptx():
                if not self._install_python_pptx():
                    self._handle_error("Не удалось установить python-pptx")
                    return False

            from pdf2image import convert_from_path
            from pptx import Presentation
            from pptx.util import Inches

            self._update_status(f"Конвертация PDF в изображения (DPI={self.dpi})...")
            self._update_progress(30)

            # Конвертируем PDF в изображения
            images = convert_from_path(
                str(input_path),
                dpi=self.dpi,
                fmt='png'
            )

            self._update_status(f"Создание презентации с {len(images)} слайдами...")
            self._update_progress(60)

            # Создаем презентацию
            prs = Presentation()

            # Настройка размера слайда (16:9)
            prs.slide_width = Inches(10)
            prs.slide_height = Inches(5.625)

            for i, img in enumerate(images):
                self._update_progress(60 + int((i / len(images)) * 35))

                # Добавляем слайд
                slide_layout = prs.slide_layouts[6]  # Пустой слайд
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

                self._update_status(f"Слайд {i+1}/{len(images)} добавлен")

            # Сохраняем презентацию
            self._update_status("Сохранение презентации...")
            prs.save(str(output_path))

            self._update_progress(100)
            self._update_status(f"Конвертация завершена! Создано {len(images)} слайдов")

            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в PPTX")
            return False