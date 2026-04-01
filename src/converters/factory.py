"""
Фабрика для создания конвертеров
"""
from typing import Optional
from pathlib import Path
from .base import BaseConverter
from .docx_to_pdf import DocxToPdfConverter
from .pptx_to_pdf import PptxToPdfConverter
from .image_converter import ImageConverter
from src.config.formats import (
    SUPPORTED_CONVERSIONS,
    ALL_INPUT_FORMATS,
    ALL_OUTPUT_FORMATS,
    get_output_formats_for_input,
    can_convert,
    get_converter_class
)
from loguru import logger


class ConverterFactory:
    """Фабрика для создания конвертеров"""

    @classmethod
    def get_converter(cls, input_ext: str, output_ext: str, **kwargs) -> Optional[BaseConverter]:
        """
        Возвращает подходящий конвертер для заданных форматов
        """
        input_ext = input_ext.lower().lstrip('.')
        output_ext = output_ext.lower().lstrip('.')

        # Проверяем, поддерживается ли конвертация
        if not can_convert(input_ext, output_ext):
            logger.warning(f"Конвертация {input_ext} -> {output_ext} не поддерживается")
            return None

        # Создаем конвертер
        converter_class = get_converter_class(input_ext, output_ext)
        
        if converter_class == 'DocxToPdfConverter':
            return DocxToPdfConverter()
        elif converter_class == 'PptxToPdfConverter':
            return PptxToPdfConverter()
        elif converter_class == 'ImageConverter':
            converter = ImageConverter()
            if 'quality' in kwargs:
                converter.set_quality(kwargs['quality'])
            if 'max_width' in kwargs or 'max_height' in kwargs:
                converter.set_max_size(
                    kwargs.get('max_width'),
                    kwargs.get('max_height')
                )
            return converter
        
        logger.error(f"Неизвестный конвертер: {converter_class}")
        return None

    @classmethod
    def get_supported_conversions(cls) -> list[tuple[str, str]]:
        """Возвращает список всех поддерживаемых конвертаций"""
        return list(SUPPORTED_CONVERSIONS.keys())

    @classmethod
    def get_input_formats(cls) -> list[str]:
        """Возвращает список всех поддерживаемых входных форматов"""
        return ALL_INPUT_FORMATS

    @classmethod
    def get_output_formats(cls) -> list[str]:
        """Возвращает список всех поддерживаемых выходных форматов"""
        return ALL_OUTPUT_FORMATS

    @classmethod
    def get_output_formats_for_input(cls, input_ext: str) -> list[str]:
        """Возвращает возможные выходные форматы для данного входного"""
        return get_output_formats_for_input(input_ext)

    @classmethod
    def can_convert(cls, input_ext: str, output_ext: str) -> bool:
        """Проверяет, поддерживается ли конвертация"""
        return can_convert(input_ext, output_ext)