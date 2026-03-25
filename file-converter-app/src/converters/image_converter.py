"""
Конвертер изображений с поддержкой различных форматов
"""
from pathlib import Path
from PIL import Image
from .base import BaseConverter
from loguru import logger


class ImageConverter(BaseConverter):
    """Конвертер изображений (PNG, JPG, JPEG, WEBP, BMP)"""

    def __init__(self, quality: int = 85, max_width: int = None, max_height: int = None):
        super().__init__()
        self.quality = quality
        self.max_width = max_width
        self.max_height = max_height

    def get_input_formats(self) -> list[str]:
        return ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff']

    def get_output_formats(self) -> list[str]:
        return ['png', 'jpg', 'jpeg', 'webp', 'bmp']

    def set_quality(self, quality: int):
        """Устанавливает качество для JPEG (1-100)"""
        self.quality = max(1, min(100, quality))

    def set_max_size(self, width: int = None, height: int = None):
        """Устанавливает максимальные размеры изображения"""
        self.max_width = width
        self.max_height = height

    def convert(self, input_path: Path, output_path: Path) -> bool:
        """
        Конвертирует изображение в указанный формат
        """
        try:
            self._update_status("Открытие изображения...")
            self._update_progress(10)

            # Открываем изображение
            with Image.open(input_path) as img:
                self._update_progress(30)

                # Конвертируем RGBA в RGB для JPEG
                output_format = output_path.suffix.lower().lstrip('.')
                if output_format in ['jpg', 'jpeg'] and img.mode == 'RGBA':
                    self._update_status("Конвертация цветового пространства...")
                    # Создаем белый фон
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                    img = background

                # Изменяем размер если нужно
                if self.max_width or self.max_height:
                    self._update_status("Изменение размера...")
                    img.thumbnail((self.max_width or img.width,
                                   self.max_height or img.height),
                                  Image.Resampling.LANCZOS)

                self._update_progress(60)

                # Определяем параметры сохранения
                save_kwargs = {}
                if output_format in ['jpg', 'jpeg']:
                    save_kwargs['quality'] = self.quality
                    save_kwargs['optimize'] = True
                elif output_format == 'webp':
                    save_kwargs['quality'] = self.quality
                elif output_format == 'png':
                    save_kwargs['compress_level'] = 6

                self._update_status(f"Сохранение в {output_format.upper()}...")
                img.save(output_path, **save_kwargs)

                self._update_progress(100)
                self._update_status("Конвертация завершена!")

                return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации изображения: {str(e)}")
            return False