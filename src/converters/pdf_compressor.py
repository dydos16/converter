"""
Сжатие и оптимизация PDF
"""
import shutil
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfCompressor(BaseConverter):
    """Конвертер для сжатия PDF"""

    def __init__(self):
        super().__init__()
        self.compression_level = 6  # 0-9, где 9 - максимальное сжатие
        self.remove_metadata = False
        self.optimize_images = True

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['pdf']

    def set_compression(self, level: int):
        """Устанавливает уровень сжатия (0-9)"""
        self.compression_level = max(0, min(9, level))

    def set_remove_metadata(self, remove: bool):
        """Удалять метаданные"""
        self.remove_metadata = remove

    def set_optimize_images(self, optimize: bool):
        """Оптимизировать изображения"""
        self.optimize_images = optimize

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Сжатие PDF...")
            self._update_progress(10)

            # Пробуем использовать PyMuPDF
            try:
                import fitz

                self._update_status(f"Уровень сжатия: {self.compression_level}")
                self._update_progress(30)

                doc = fitz.open(str(input_path))

                # Вес PDF — в основном картинки (сканы, фото): пересжимаем их с меньшим разрешением.
                # Уровень 4–6 — до 150 DPI, качество 80; 7–9 — до 100 DPI, качество 60.
                # Чёрно-белые сканы (1 бит) не трогаем: в JPEG они только вырастут
                if self.optimize_images and self.compression_level >= 4:
                    self._update_status("Сжатие картинок...")
                    dpi, quality = (150, 80) if self.compression_level <= 6 else (100, 60)
                    doc.rewrite_images(dpi_threshold=dpi + 50, dpi_target=dpi, quality=quality, bitonal=False)

                if self.remove_metadata:
                    self._update_status("Удаление метаданных...")
                    doc.set_metadata({})

                self._update_status("Оптимизация...")
                self._update_progress(50)
                # garbage у PyMuPDF — от 0 до 4; один save со всеми настройками (второй save их терял)
                doc.save(str(output_path), garbage=min(4, self.compression_level), clean=True, deflate=True,
                         deflate_images=True, deflate_fonts=True)
                doc.close()

                # Уже сжатый PDF может только вырасти — тогда оставляем исходный
                if output_path.stat().st_size >= input_path.stat().st_size and not self.remove_metadata:
                    shutil.copyfile(input_path, output_path)

                # Проверяем размер
                original_size = input_path.stat().st_size
                new_size = output_path.stat().st_size
                saved_percent = (1 - new_size / original_size) * 100

                self._update_progress(100)
                self._update_status(
                    f"Сжатие завершено!\n"
                    f"Исходный: {original_size / 1024:.1f} KB\n"
                    f"После сжатия: {new_size / 1024:.1f} KB\n"
                    f"Сэкономлено: {saved_percent:.1f}%"
                )

                return True

            except ImportError:
                # Если PyMuPDF нет, используем Ghostscript
                self._update_status("PyMuPDF не установлен, пробуем Ghostscript...")
                return self._compress_with_ghostscript(input_path, output_path)

        except Exception as e:
            self._handle_error(f"Ошибка сжатия PDF: {str(e)}")
            logger.exception("Ошибка сжатия PDF")
            return False

    def _compress_with_ghostscript(self, input_path: Path, output_path: Path) -> bool:
        """Сжимает PDF через Ghostscript"""
        import shutil
        import platform

        # Ghostscript имеет разные имена бинарника на разных ОС
        gs_path = None
        if platform.system().lower() == 'windows':
            for name in ['gswin64c', 'gswin32c', 'gs']:
                gs_path = shutil.which(name)
                if gs_path:
                    break
        else:
            gs_path = shutil.which('gs')

        if not gs_path:
            self._handle_error(
                "Ghostscript не найден!\n\n"
                "Для сжатия PDF установите Ghostscript:\n"
                "- macOS: brew install ghostscript\n"
                "- Windows: https://ghostscript.com/releases/gsdnld.html\n"
                "- Linux: sudo apt install ghostscript"
            )
            return False

        # Уровни качества Ghostscript
        quality_levels = {
            0: 'default',
            3: 'screen',  # низкое качество, маленький размер
            6: 'ebook',  # среднее качество
            9: 'printer'  # высокое качество, большой размер
        }

        quality = quality_levels.get(self.compression_level, 'ebook')

        cmd = [
            gs_path,
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/' + quality,
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            f'-sOutputFile={output_path}',
            str(input_path)
        ]

        try:
            self._update_status(f"Используем Ghostscript (качество: {quality})...")
            self._update_progress(50)

            result = subprocess.run(cmd, capture_output=True, timeout=300)

            if result.returncode == 0 and output_path.exists():
                self._update_progress(100)
                self._update_status("Сжатие завершено!")
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка Ghostscript: {e}")
            return False