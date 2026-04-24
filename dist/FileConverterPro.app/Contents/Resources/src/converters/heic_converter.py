"""
Конвертер HEIC изображений (iPhone формат)
"""
import sys
import subprocess
import platform
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
        """Пытается установить pyheif без brew (через wheel)"""
        try:
            self._update_status("Установка pyheif...")

            system = platform.system().lower()
            python_version = f"{sys.version_info.major}{sys.version_info.minor}"

            # Пробуем три стратегии:
            # 1. Обычный pip (вдруг уже есть libheif в системе)
            # 2. Предкомпилированный wheel для Windows/macOS (содержит libheif внутри)
            # 3. Сообщение о необходимости libheif

            # Стратегия 1: обычный pip install
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', 'pyheif', '--quiet'
                ])
                self.heic_available = self._check_heic()
                if self.heic_available:
                    return True
            except Exception:
                pass

            # Стратегия 2: wheel для Windows (там libheif внутри)
            if system == 'windows':
                wheel_map = {
                    '311': 'pyheif-0.8.0-cp311-cp311-win_amd64.whl',
                    '310': 'pyheif-0.8.0-cp310-cp310-win_amd64.whl',
                    '39': 'pyheif-0.8.0-cp39-cp39-win_amd64.whl',
                }
                wheel_name = wheel_map.get(python_version)
                if wheel_name:
                    wheel_url = f"https://github.com/FIRC/pythonlibs_whl_mirror/raw/master/pyheif/{wheel_name}"
                    try:
                        subprocess.check_call([
                            sys.executable, '-m', 'pip', 'install', wheel_url, '--quiet'
                        ])
                        self.heic_available = self._check_heic()
                        if self.heic_available:
                            return True
                    except Exception:
                        pass

            # Стратегия 2б: wheel для macOS arm64 (M1/M2) - экспериментально
            if system == 'darwin':
                # Для macOS готовых wheel с libheif внутри практически нет
                # Пробуем альтернативу pillow_heif (более лёгкая)
                try:
                    subprocess.check_call([
                        sys.executable, '-m', 'pip', 'install', 'pillow-heif', '--quiet'
                    ])
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                    self.heic_available = self._check_heic()
                    if self.heic_available:
                        return True
                except Exception:
                    pass

            # Если ничего не помогло — даём инструкцию
            if system == 'darwin':
                self._handle_error(
                    "❌ Не удалось установить поддержку HEIC\n\n"
                    "Установите вручную:\n"
                    "   brew install libheif\n"
                    "   pip install pyheif\n\n"
                    "Или используйте альтернативу:\n"
                    "   pip install pillow-heif"
                )
            elif system == 'linux':
                self._handle_error(
                    "❌ Не удалось установить поддержку HEIC\n\n"
                    "Установите вручную:\n"
                    "   sudo apt install libheif-dev\n"
                    "   pip install pyheif"
                )
            else:
                self._handle_error(
                    "❌ Не удалось установить поддержку HEIC\n"
                    "Скачайте pyheif wheel для вашей системы:\n"
                    "   https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyheif"
                )

            return False

        except Exception as e:
            logger.error(f"Ошибка установки HEIC: {e}")
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