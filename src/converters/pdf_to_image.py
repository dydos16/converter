"""
PDF to Image - конвертирует PDF в изображения
"""
import sys
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional
from PIL import Image
from .base import BaseConverter
from loguru import logger


class PdfToImageConverter(BaseConverter):
    """Конвертер PDF в изображения"""

    def __init__(self, quality: int = 85, dpi: int = 200):
        super().__init__()
        self.quality = quality
        self.dpi = dpi
        self.pdf2image_available = self._check_pdf2image()
        self.pymupdf_available = self._check_pymupdf()
        self.page_range = None  # Диапазон страниц, например "1-5,10,15-20"

    def _check_pdf2image(self):
        """Проверяет доступность pdf2image"""
        try:
            from pdf2image import convert_from_path
            return True
        except ImportError:
            return False

    def _check_pymupdf(self):
        """Проверяет доступность PyMuPDF"""
        try:
            import fitz
            return True
        except ImportError:
            return False

    def _install_pdf2image(self):
        """Устанавливает pdf2image"""
        try:
            self._update_status("Установка pdf2image...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'pdf2image', '--quiet'
            ])
            self.pdf2image_available = True
            self._update_status("pdf2image успешно установлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки pdf2image: {e}")
            return False

    def _install_pymupdf(self):
        """Устанавливает PyMuPDF"""
        try:
            self._update_status("Установка PyMuPDF...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'PyMuPDF', '--quiet'
            ])
            self.pymupdf_available = True
            self._update_status("PyMuPDF успешно установлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки PyMuPDF: {e}")
            return False

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['png', 'jpg', 'jpeg', 'webp']

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
        """Парсит диапазон страниц, например '1-5,10,15-20'"""
        if not self.page_range:
            return list(range(total_pages))

        pages = set()
        parts = self.page_range.split(',')

        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                pages.update(range(max(1, start), min(total_pages, end) + 1))
            else:
                page_num = int(part)
                if 1 <= page_num <= total_pages:
                    pages.add(page_num)

        return sorted(pages)

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Подготовка к конвертации PDF в изображения...")
            self._update_progress(10)

            # Пробуем использовать PyMuPDF (быстрее, не требует poppler)
            if self.pymupdf_available:
                return self._convert_with_pymupdf(input_path, output_path)

            # Если PyMuPDF нет, используем pdf2image
            if not self.pdf2image_available:
                if not self._install_pdf2image():
                    self._handle_error("Не удалось установить pdf2image")
                    return False

            return self._convert_with_pdf2image(input_path, output_path)

        except Exception as e:
            self._handle_error(f"Ошибка конвертации PDF в изображения: {str(e)}")
            logger.exception("Ошибка конвертации PDF в изображения")
            return False

    def _convert_with_pymupdf(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует PDF в изображения с помощью PyMuPDF"""
        try:
            import fitz

            self._update_status("Используем PyMuPDF для конвертации...")
            self._update_progress(20)

            doc = fitz.open(str(input_path))
            total_pages = len(doc)

            # Парсим диапазон страниц
            pages_to_convert = self._parse_page_range(total_pages)

            if not pages_to_convert:
                self._handle_error("Не выбрано ни одной страницы для конвертации")
                return False

            output_format = output_path.suffix.lower().lstrip('.')
            output_dir = output_path.parent
            base_name = output_path.stem

            images = []

            for idx, page_num in enumerate(pages_to_convert):
                self._update_progress(20 + int((idx / len(pages_to_convert)) * 70))

                page = doc[page_num - 1]  # Страницы в PyMuPDF с 0

                # Увеличиваем разрешение
                zoom = self.dpi / 72  # 72 dpi - базовое разрешение PDF
                mat = fitz.Matrix(zoom, zoom)

                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Конвертируем в PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                images.append(img)

                self._update_status(f"Обработана страница {page_num} из {len(pages_to_convert)}")

            doc.close()

            self._update_progress(90)

            # Сохраняем изображения
            if len(images) == 1:
                # Одна страница - сохраняем напрямую
                return self._save_single_image(images[0], output_path, output_format)
            else:
                # Несколько страниц - создаем ZIP архив
                return self._save_multiple_images(images, output_path, output_format, base_name, output_dir)

        except Exception as e:
            logger.error(f"Ошибка в PyMuPDF: {e}")
            return False

    def _convert_with_pdf2image(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует PDF в изображения с помощью pdf2image"""
        try:
            from pdf2image import convert_from_path

            self._update_status("Используем pdf2image для конвертации...")
            self._update_progress(20)

            # Конвертируем PDF в изображения
            images = convert_from_path(
                str(input_path),
                dpi=self.dpi,
                fmt='png'  # Сначала в PNG для лучшего качества
            )

            total_pages = len(images)

            # Парсим диапазон страниц
            pages_to_convert = self._parse_page_range(total_pages)

            if not pages_to_convert:
                self._handle_error("Не выбрано ни одной страницы для конвертации")
                return False

            # Выбираем нужные страницы
            selected_images = [images[page_num - 1] for page_num in pages_to_convert]

            self._update_progress(50)

            output_format = output_path.suffix.lower().lstrip('.')
            output_dir = output_path.parent
            base_name = output_path.stem

            self._update_status(f"Сохранение {len(selected_images)} изображений...")

            # Сохраняем изображения
            if len(selected_images) == 1:
                return self._save_single_image(selected_images[0], output_path, output_format)
            else:
                return self._save_multiple_images(
                    selected_images, output_path, output_format,
                    base_name, output_dir, pages_to_convert
                )

        except Exception as e:
            logger.error(f"Ошибка в pdf2image: {e}")
            return False

    def _save_single_image(self, img: Image.Image, output_path: Path, output_format: str) -> bool:
        """Сохраняет одно изображение"""
        try:
            self._update_status("Сохранение изображения...")
            self._update_progress(80)

            # Конвертируем в RGB для JPEG
            if output_format in ['jpg', 'jpeg'] and img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                img = background

            save_kwargs = {}
            if output_format in ['jpg', 'jpeg']:
                save_kwargs['quality'] = self.quality
                save_kwargs['optimize'] = True
            elif output_format == 'webp':
                save_kwargs['quality'] = self.quality
            elif output_format == 'png':
                save_kwargs['compress_level'] = 6

            img.save(output_path, **save_kwargs)

            self._update_progress(100)
            self._update_status("Изображение успешно сохранено!")

            return True

        except Exception as e:
            self._handle_error(f"Ошибка сохранения изображения: {str(e)}")
            return False

    def _save_multiple_images(self, images: List[Image.Image], output_path: Path,
                              output_format: str, base_name: str, output_dir: Path,
                              page_numbers: Optional[List[int]] = None) -> bool:
        """Сохраняет несколько изображений в ZIP архив"""
        try:
            self._update_status(f"Создание ZIP архива с {len(images)} изображениями...")

            zip_path = output_path.with_suffix('.zip')

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, img in enumerate(images):
                    self._update_progress(80 + int((i / len(images)) * 20))

                    # Определяем имя файла
                    if page_numbers:
                        page_num = page_numbers[i]
                        filename = f"{base_name}_page_{page_num}.{output_format}"
                    else:
                        filename = f"{base_name}_page_{i + 1}.{output_format}"

                    # Конвертируем в RGB для JPEG
                    if output_format in ['jpg', 'jpeg'] and img.mode == 'RGBA':
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                        img = background

                    save_kwargs = {}
                    if output_format in ['jpg', 'jpeg']:
                        save_kwargs['quality'] = self.quality
                        save_kwargs['optimize'] = True
                    elif output_format == 'webp':
                        save_kwargs['quality'] = self.quality
                    elif output_format == 'png':
                        save_kwargs['compress_level'] = 6

                    # Сохраняем во временный файл
                    with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as tmp:
                        img.save(tmp.name, **save_kwargs)
                        zipf.write(tmp.name, filename)
                        Path(tmp.name).unlink()

                    self._update_status(f"Добавлена страница {i + 1} из {len(images)}")

            self._update_progress(100)
            self._update_status(f"Создан архив: {zip_path.name} ({len(images)} страниц)")

            return True

        except Exception as e:
            self._handle_error(f"Ошибка создания архива: {str(e)}")
            return False