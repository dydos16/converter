"""
Фабрика для создания конвертеров на основе форматов файлов
"""
from typing import Optional, Dict, Type
from pathlib import Path
from .base import BaseConverter
from .docx_to_pdf import DocxToPdfConverter
from .image_converter import ImageConverter
from loguru import logger


class ConverterFactory:
    """Фабрика для создания конвертеров"""

    # Регистр конвертеров
    _converters: Dict[str, Type[BaseConverter]] = {}

    @classmethod
    def register(cls, name: str, converter_class: Type[BaseConverter]):
        """Регистрирует новый тип конвертера"""
        cls._converters[name] = converter_class
        logger.info(f"Зарегистрирован конвертер: {name}")

    @classmethod
    def get_converter(cls, input_ext: str, output_ext: str, **kwargs) -> Optional[BaseConverter]:
        """
        Возвращает подходящий конвертер для заданных форматов

        Args:
            input_ext: Входное расширение файла
            output_ext: Выходное расширение файла
            **kwargs: Дополнительные параметры для конвертера

        Returns:
            BaseConverter или None, если конвертер не найден
        """
        input_ext = input_ext.lower().lstrip('.')
        output_ext = output_ext.lower().lstrip('.')

        # DOCX/DOC -> PDF
        if input_ext in ['docx', 'doc'] and output_ext == 'pdf':
            return DocxToPdfConverter()

        # Изображения
        if input_ext in ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'] and \
                output_ext in ['png', 'jpg', 'jpeg', 'webp', 'bmp']:
            converter = ImageConverter()
            if 'quality' in kwargs:
                converter.set_quality(kwargs['quality'])
            if 'max_width' in kwargs or 'max_height' in kwargs:
                converter.set_max_size(
                    kwargs.get('max_width'),
                    kwargs.get('max_height')
                )
            return converter

        return None

    @classmethod
    def get_supported_conversions(cls) -> list[tuple[str, str]]:
        """Возвращает список всех поддерживаемых конвертаций"""
        return [
            ('docx', 'pdf'),
            ('doc', 'pdf'),
            ('png', 'jpg'),
            ('png', 'jpeg'),
            ('jpg', 'png'),
            ('jpeg', 'png'),
            ('png', 'webp'),
            ('webp', 'png'),
            ('bmp', 'png'),
            ('gif', 'png'),
            ('tiff', 'png'),
        ]

    @classmethod
    def get_input_formats(cls) -> list[str]:
        """Возвращает список всех поддерживаемых входных форматов"""
        formats = set()
        for input_ext, _ in cls.get_supported_conversions():
            formats.add(input_ext)
        return sorted(list(formats))

    @classmethod
    def get_output_formats_for_input(cls, input_ext: str) -> list[str]:
        """Возвращает возможные выходные форматы для данного входного"""
        input_ext = input_ext.lower().lstrip('.')
        output_formats = []

        for in_ext, out_ext in cls.get_supported_conversions():
            if in_ext == input_ext:
                output_formats.append(out_ext)

        return sorted(list(set(output_formats)))