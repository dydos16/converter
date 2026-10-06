"""
Конвертер изображений с поддержкой различных форматов
"""
import io
import zipfile
from pathlib import Path
from PIL import Image, ImageOps
from .base import BaseConverter
from loguru import logger

# Файлы — самого пользователя, а не из интернета: панорамы и сканы бывают больше 178 Мпикс (порог «защиты
# от бомб» в Pillow). Гигапиксель — около 3 ГБ памяти в RGB
Image.MAX_IMAGE_PIXELS = 1_000_000_000
PIL_FORMATS = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP', 'bmp': 'BMP', 'gif': 'GIF',
               'tiff': 'TIFF'}


def fit_mode(img: Image.Image, output_format: str) -> Image.Image:
    """Приводит картинку к режиму, который умеет записать формат."""
    has_alpha = img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info
    if output_format in ('jpg', 'jpeg'):
        if has_alpha:
            # У JPEG нет прозрачности: подкладываем белый фон (иначе прозрачное становится чёрным)
            rgba = img.convert('RGBA')
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel('A'))
            return background
        return img if img.mode in ('RGB', 'L', 'CMYK') else img.convert('RGB')
    # PNG/WebP/BMP/GIF не пишут CMYK, 16-битные и прочие редкие режимы
    if img.mode in ('1', 'L', 'P', 'RGB', 'RGBA'):
        return img
    return img.convert('RGBA' if has_alpha else 'RGB')


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

            with Image.open(input_path) as source:
                output_format = output_path.suffix.lower().lstrip('.')
                frames = getattr(source, 'n_frames', 1)
                if frames > 1 and source.format == 'TIFF':
                    return self._save_pages(source, output_path, output_format)
                if frames > 1 and output_format == 'webp':
                    # Анимация (GIF) → анимированный WebP, а не первый кадр
                    source.save(output_path, 'WEBP', save_all=True, quality=self.quality,
                                duration=source.info.get('duration', 100), loop=source.info.get('loop', 0))
                    self._update_progress(100)
                    return True

                # Фото с телефона хранят поворот в EXIF: применяем его, иначе снимок ляжет на бок
                img = ImageOps.exif_transpose(source)
                img = fit_mode(img, output_format)
                self._update_progress(30)

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
                if output_format in ('jpg', 'jpeg', 'png', 'webp', 'tiff'):
                    # Дата съёмки, камера и цветовой профиль (iPhone снимает в Display P3) — переносим.
                    # Профиль годится, только если цветовой режим не поменялся
                    exif = img.getexif()
                    if exif:
                        save_kwargs['exif'] = exif
                    if img.mode == source.mode and source.info.get('icc_profile'):
                        save_kwargs['icc_profile'] = source.info['icc_profile']

                self._update_status(f"Сохранение в {output_format.upper()}...")
                img.save(output_path, **save_kwargs)

                self._update_progress(100)
                self._update_status("Конвертация завершена!")

                return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации изображения: {str(e)}")
            return False

    def _save_pages(self, source: Image.Image, output_path: Path, output_format: str) -> bool:
        """Многостраничный TIFF (факс, скан) → архив со всеми страницами, как у PDF → картинки."""
        from src.utils.helpers import get_unique_filename
        zip_path = get_unique_filename(output_path.with_suffix('.zip'))
        quality = {'quality': self.quality} if output_format in ('jpg', 'jpeg', 'webp') else {}
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for n in range(source.n_frames):
                self._update_progress(int(n / source.n_frames * 100))
                source.seek(n)
                buffer = io.BytesIO()
                fit_mode(source.copy(), output_format).save(buffer, PIL_FORMATS[output_format], **quality)
                archive.writestr(f"{output_path.stem}_page_{n + 1}.{output_format}", buffer.getvalue())
        self._update_status(f"Создан архив: {zip_path.name} ({source.n_frames} страниц)")
        return True
