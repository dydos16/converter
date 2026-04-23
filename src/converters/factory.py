"""
Фабрика для создания конвертеров
"""
from typing import Optional
from pathlib import Path
from .base import BaseConverter
from .docx_to_pdf import DocxToPdfConverter
from .pptx_to_pdf import PptxToPdfConverter
from .image_converter import ImageConverter
from .pdf_to_pptx import PdfToPptxConverter
from .pdf_to_docx import PdfToDocxConverter
from .pdf_to_text import PdfToTextConverter
from .pdf_to_image import PdfToImageConverter
from .pdf_compressor import PdfCompressor
from .pdf_to_spreadsheet import PdfToSpreadsheetConverter
from .pdf_to_html import PdfToHtmlConverter
from .pdf_to_json import PdfToJsonConverter
from .pdf_to_xml import PdfToXmlConverter
from .pdf_to_markdown import PdfToMarkdownConverter
from .spreadsheet_converter import SpreadsheetConverter
from .text_document_converter import TextDocumentConverter
from .heic_converter import HeicConverter
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

    # Словарь маппинга имен классов на сами классы
    _CONVERTER_MAP = {
        'DocxToPdfConverter': DocxToPdfConverter,
        'PptxToPdfConverter': PptxToPdfConverter,
        'ImageConverter': ImageConverter,
        'PdfToPptxConverter': PdfToPptxConverter,
        'PdfToDocxConverter': PdfToDocxConverter,
        'PdfToTextConverter': PdfToTextConverter,
        'PdfToImageConverter': PdfToImageConverter,
        'PdfCompressor': PdfCompressor,
        'PdfToSpreadsheetConverter': PdfToSpreadsheetConverter,
        'PdfToHtmlConverter': PdfToHtmlConverter,
        'PdfToJsonConverter': PdfToJsonConverter,
        'PdfToXmlConverter': PdfToXmlConverter,
        'PdfToMarkdownConverter': PdfToMarkdownConverter,
        'SpreadsheetConverter': SpreadsheetConverter,
        'TextDocumentConverter': TextDocumentConverter,
        'HeicConverter': HeicConverter,
    }

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

        # Получаем имя класса конвертера
        converter_class_name = get_converter_class(input_ext, output_ext)

        # Получаем класс из словаря
        converter_class = cls._CONVERTER_MAP.get(converter_class_name)

        if not converter_class:
            logger.error(f"Неизвестный конвертер: {converter_class_name}")
            return None

        # Создаем экземпляр
        converter = converter_class()

        # Применяем параметры конфигурации
        cls._apply_converter_settings(converter, converter_class_name, kwargs)

        return converter

    @classmethod
    def _apply_converter_settings(cls, converter: BaseConverter, converter_class_name: str, kwargs: dict):
        """Применяет настройки к конвертеру"""

        # Настройки для ImageConverter
        if converter_class_name == 'ImageConverter':
            if 'quality' in kwargs:
                converter.set_quality(kwargs['quality'])
            if 'max_width' in kwargs or 'max_height' in kwargs:
                converter.set_max_size(
                    kwargs.get('max_width'),
                    kwargs.get('max_height')
                )

        # Настройки для PdfToPptxConverter
        elif converter_class_name == 'PdfToPptxConverter':
            if 'dpi' in kwargs:
                converter.dpi = kwargs['dpi']
            if 'quality' in kwargs:
                converter.quality = kwargs['quality']

        # Настройки для PdfToDocxConverter
        elif converter_class_name == 'PdfToDocxConverter':
            if 'extract_text_only' in kwargs:
                converter.set_extract_text_only(kwargs['extract_text_only'])

        # Настройки для PdfToImageConverter
        elif converter_class_name == 'PdfToImageConverter':
            if 'quality' in kwargs:
                converter.set_quality(kwargs['quality'])
            if 'dpi' in kwargs:
                converter.set_dpi(kwargs['dpi'])
            if 'page_range' in kwargs:
                converter.set_page_range(kwargs['page_range'])

        # Настройки для PdfCompressor
        elif converter_class_name == 'PdfCompressor':
            if 'compression_level' in kwargs:
                converter.set_compression(kwargs['compression_level'])
            if 'remove_metadata' in kwargs:
                converter.set_remove_metadata(kwargs['remove_metadata'])
            if 'optimize_images' in kwargs:
                converter.set_optimize_images(kwargs['optimize_images'])

        # Настройки для HeicConverter
        elif converter_class_name == 'HeicConverter':
            if 'quality' in kwargs:
                converter.set_quality(kwargs['quality'])

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