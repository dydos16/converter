"""
Управление настройками приложения
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger


class Settings:
    """Класс для управления настройками приложения"""

    DEFAULT_SETTINGS = {
        # Общие настройки
        'theme': 'system',
        'max_concurrent_jobs': 4,
        'output_directory': str(Path.home() / 'Downloads'),
        'auto_open_folder': True,
        'keep_original_name': True,
        'show_notifications': True,

        # Настройки изображений
        'image_quality': 85,
        'image_max_width': None,
        'image_max_height': None,

        # Настройки PDF
        'pdf_dpi': 200,
        'pdf_quality': 85,
        'pdf_page_range': '',
        'pdf_compress_level': 6,
        'pdf_remove_metadata': False,
        'pdf_optimize_images': True,
        'pdf_table_strategy': 'auto',  # auto, lattice, stream

        # Настройки HEIC
        'heic_quality': 85,

        # История
        'recent_files': [],
        'recent_formats': []
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            from src.utils.helpers import get_config_dir
            config_path = get_config_dir() / 'settings.json'

        self.config_path = config_path
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        """Загружает настройки из файла"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
                    logger.info(f"Настройки загружены из {self.config_path}")
        except Exception as e:
            logger.warning(f"Не удалось загрузить настройки: {e}")

    def save(self):
        """Сохраняет настройки в файл"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Настройки сохранены в {self.config_path}")
        except Exception as e:
            logger.error(f"Не удалось сохранить настройки: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение настройки"""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Устанавливает значение настройки"""
        self.settings[key] = value
        self.save()

    def update(self, values: Dict[str, Any]):
        """Устанавливает несколько значений и пишет файл один раз"""
        self.settings.update(values)
        self.save()

    def add_recent_format(self, input_ext: str, output_ext: str):
        """Добавляет формат в список недавних"""
        format_pair = f"{input_ext}→{output_ext}"
        recent = self.settings.get('recent_formats', [])

        if format_pair in recent:
            recent.remove(format_pair)

        recent.insert(0, format_pair)
        self.settings['recent_formats'] = recent[:10]
        self.save()