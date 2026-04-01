"""
Конвертер HEIC изображений (iPhone формат)
"""
import sys
import subprocess
from pathlib import Path
from PIL import Image
from .base import BaseConverter
from loguru import logger


class HeicConverter(BaseConverter):
    """Конвертер HEIC в другие форматы"""

    def __init__(self):
        super().__init__()
        self.quality = 85
        self.heic_available = self._check_heic()

    def _check_heic(self):
        """Проверяет доступность pyheif"""
        try:
            import pyheif
            return True
        except ImportError:
            return False

    def _install_heic(self):
        """Устанавливает pyheif"""
        try:
            self._update_status("Установка pyheif...")

            # Для macOS可能需要额外的库
            import platform
            if platform.system().lower() == 'darwin':
                subprocess.check_call(['brew', 'install', 'libheif'], capture_output=True)

            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'pyheif', '--quiet'
            ])
            self.heic_available = True
            return True
        except Exception as e:
            logger.error(f"Ошибка установки pyheif: {e}")
            return False

    def get_input_formats(self):
        return ['heic', 'heif']

    def get_output_formats(self):
        return ['jpg', 'jpeg', 'png', 'webp']

    def set_quality(self, quality: int):
        """Устанавливает качество для JPEG/WebP"""
        self.quality = max(1, min(100, quality))

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Конвертация HEIC...")
            self._update_progress(10)

            if not self.heic_available:
                if not self._install_heic():
                    self._handle_error(
                        "Не удалось установить pyheif\n\n"
                        "Для macOS также требуется: brew install libheif"
                    )
                    return False

            import pyheif

            self._update_status("Чтение HEIC файла...")
            self._update_progress(30)

            # Читаем HEIC
            with open(input_path, 'rb') as f:
                heif_file = pyheif.read(f.read())

            # Конвертируем в PIL Image
            img = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )

            self._update_progress(60)

            output_format = output_path.suffix.lower().lstrip('.')

            # Конвертируем в RGB для JPEG
            if output_format in ['jpg', 'jpeg'] and img.mode == 'RGBA':
                self._update_status("Конвертация цветового пространства...")
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                img = background

            self._update_status(f"Сохранение в {output_format.upper()}...")
            self._update_progress(80)

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
            self._update_status("Конвертация завершена!")

            return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации HEIC: {str(e)}")
            logger.exception("Ошибка конвертации HEIC")
            return False