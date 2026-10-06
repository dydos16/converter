"""
Конвертер HEIC изображений (iPhone формат)
"""
from .image_converter import ImageConverter


class HeicConverter(ImageConverter):
    """HEIC/HEIF → jpg/png/webp: файл открывает pillow-heif, дальше — как обычная картинка
    (поворот из EXIF, дата съёмки, цветовой профиль Display P3)."""

    def __init__(self):
        super().__init__()
        import pillow_heif
        pillow_heif.register_heif_opener()

    def get_input_formats(self):
        return ['heic', 'heif']

    def get_output_formats(self):
        return ['jpg', 'jpeg', 'png', 'webp']
