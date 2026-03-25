"""
Фабрика для создания конвертеров
"""
from typing import Optional, Dict, Type
from pathlib import Path
from .base import BaseConverter
from .docx_to_pdf import DocxToPdfConverter
from .pptx_to_pdf import PptxToPdfConverter
from .image_converter import ImageConverter
from loguru import logger


class ConverterFactory:
    """Фабрика для создания конвертеров"""

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

        # Word -> PDF
        if input_ext in ['docx', 'doc'] and output_ext == 'pdf':
            return DocxToPdfConverter()

        # PowerPoint -> PDF
        if input_ext in ['pptx', 'ppt', 'pps', 'ppsx'] and output_ext == 'pdf':
            return PptxToPdfConverter()

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

        # Если конвертер не найден
        logger.warning(f"Конвертер не найден для {input_ext} -> {output_ext}")
        return None

    @classmethod
    def get_supported_conversions(cls) -> list[tuple[str, str]]:
        """
        Возвращает список всех поддерживаемых конвертаций

        Returns:
            list[tuple[str, str]]: Список пар (входной_формат, выходной_формат)
        """
        return [
            # Word
            ('docx', 'pdf'),
            ('doc', 'pdf'),

            # PowerPoint
            ('pptx', 'pdf'),
            ('ppt', 'pdf'),
            ('pps', 'pdf'),
            ('ppsx', 'pdf'),

            # Изображения
            ('png', 'jpg'),
            ('png', 'jpeg'),
            ('png', 'webp'),
            ('png', 'bmp'),
            ('jpg', 'png'),
            ('jpg', 'jpeg'),
            ('jpg', 'webp'),
            ('jpg', 'bmp'),
            ('jpeg', 'png'),
            ('jpeg', 'jpg'),
            ('jpeg', 'webp'),
            ('jpeg', 'bmp'),
            ('webp', 'png'),
            ('webp', 'jpg'),
            ('webp', 'jpeg'),
            ('webp', 'bmp'),
            ('bmp', 'png'),
            ('bmp', 'jpg'),
            ('bmp', 'jpeg'),
            ('bmp', 'webp'),
            ('gif', 'png'),
            ('gif', 'jpg'),
            ('gif', 'webp'),
            ('tiff', 'png'),
            ('tiff', 'jpg'),
            ('tiff', 'webp'),
        ]

    @classmethod
    def get_input_formats(cls) -> list[str]:
        """
        Возвращает список всех поддерживаемых входных форматов

        Returns:
            list[str]: Список поддерживаемых входных форматов
        """
        formats = set()
        for input_ext, _ in cls.get_supported_conversions():
            formats.add(input_ext)
        return sorted(list(formats))

    @classmethod
    def get_output_formats(cls) -> list[str]:
        """
        Возвращает список всех поддерживаемых выходных форматов

        Returns:
            list[str]: Список поддерживаемых выходных форматов
        """
        formats = set()
        for _, output_ext in cls.get_supported_conversions():
            formats.add(output_ext)
        return sorted(list(formats))

    @classmethod
    def get_output_formats_for_input(cls, input_ext: str) -> list[str]:
        """
        Возвращает возможные выходные форматы для данного входного формата

        Args:
            input_ext: Входное расширение файла

        Returns:
            list[str]: Список возможных выходных форматов
        """
        input_ext = input_ext.lower().lstrip('.')
        output_formats = []

        for in_ext, out_ext in cls.get_supported_conversions():
            if in_ext == input_ext:
                output_formats.append(out_ext)

        return sorted(list(set(output_formats)))

    @classmethod
    def get_input_formats_for_output(cls, output_ext: str) -> list[str]:
        """
        Возвращает возможные входные форматы для данного выходного формата

        Args:
            output_ext: Выходное расширение файла

        Returns:
            list[str]: Список возможных входных форматов
        """
        output_ext = output_ext.lower().lstrip('.')
        input_formats = []

        for in_ext, out_ext in cls.get_supported_conversions():
            if out_ext == output_ext:
                input_formats.append(in_ext)

        return sorted(list(set(input_formats)))

    @classmethod
    def can_convert(cls, input_ext: str, output_ext: str) -> bool:
        """
        Проверяет, поддерживается ли конвертация между форматами

        Args:
            input_ext: Входное расширение файла
            output_ext: Выходное расширение файла

        Returns:
            bool: True если конвертация поддерживается
        """
        input_ext = input_ext.lower().lstrip('.')
        output_ext = output_ext.lower().lstrip('.')

        for in_ext, out_ext in cls.get_supported_conversions():
            if in_ext == input_ext and out_ext == output_ext:
                return True

        return False

    @classmethod
    def get_all_converters_info(cls) -> dict:
        """
        Возвращает информацию обо всех конвертерах

        Returns:
            dict: Словарь с информацией о конвертерах
        """
        info = {
            'word': {
                'name': 'Word to PDF',
                'input_formats': ['docx', 'doc'],
                'output_formats': ['pdf'],
                'description': 'Конвертация документов Word в PDF'
            },
            'powerpoint': {
                'name': 'PowerPoint to PDF',
                'input_formats': ['pptx', 'ppt', 'pps', 'ppsx'],
                'output_formats': ['pdf'],
                'description': 'Конвертация презентаций PowerPoint в PDF'
            },
            'images': {
                'name': 'Image Converter',
                'input_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'],
                'output_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp'],
                'description': 'Конвертация между форматами изображений'
            }
        }

        return info