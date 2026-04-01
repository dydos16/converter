"""
Конфигурация поддерживаемых форматов - единый источник правды
"""

# Поддерживаемые конвертации
SUPPORTED_CONVERSIONS = {
    # Word документы
    ('docx', 'pdf'): 'DocxToPdfConverter',
    ('doc', 'pdf'): 'DocxToPdfConverter',

    # PowerPoint презентации
    ('pptx', 'pdf'): 'PptxToPdfConverter',
    ('ppt', 'pdf'): 'PptxToPdfConverter',
    ('pps', 'pdf'): 'PptxToPdfConverter',
    ('ppsx', 'pdf'): 'PptxToPdfConverter',

    # Изображения
    ('png', 'jpg'): 'ImageConverter',
    ('png', 'jpeg'): 'ImageConverter',
    ('png', 'webp'): 'ImageConverter',
    ('png', 'bmp'): 'ImageConverter',
    ('jpg', 'png'): 'ImageConverter',
    ('jpg', 'jpeg'): 'ImageConverter',
    ('jpg', 'webp'): 'ImageConverter',
    ('jpg', 'bmp'): 'ImageConverter',
    ('jpeg', 'png'): 'ImageConverter',
    ('jpeg', 'jpg'): 'ImageConverter',
    ('jpeg', 'webp'): 'ImageConverter',
    ('jpeg', 'bmp'): 'ImageConverter',
    ('webp', 'png'): 'ImageConverter',
    ('webp', 'jpg'): 'ImageConverter',
    ('webp', 'jpeg'): 'ImageConverter',
    ('webp', 'bmp'): 'ImageConverter',
    ('bmp', 'png'): 'ImageConverter',
    ('bmp', 'jpg'): 'ImageConverter',
    ('bmp', 'jpeg'): 'ImageConverter',
    ('bmp', 'webp'): 'ImageConverter',
    ('gif', 'png'): 'ImageConverter',
    ('gif', 'jpg'): 'ImageConverter',
    ('gif', 'webp'): 'ImageConverter',
    ('tiff', 'png'): 'ImageConverter',
    ('tiff', 'jpg'): 'ImageConverter',
    ('tiff', 'webp'): 'ImageConverter',
}

# Все поддерживаемые входные форматы
ALL_INPUT_FORMATS = sorted(set(in_fmt for in_fmt, _ in SUPPORTED_CONVERSIONS.keys()))

# Все поддерживаемые выходные форматы
ALL_OUTPUT_FORMATS = sorted(set(out_fmt for _, out_fmt in SUPPORTED_CONVERSIONS.keys()))

# Группы форматов
FORMAT_GROUPS = {
    'documents': {
        'name': 'Документы',
        'input_formats': ['docx', 'doc'],
        'output_formats': ['pdf'],
        'icon': '📄'
    },
    'presentations': {
        'name': 'Презентации',
        'input_formats': ['pptx', 'ppt', 'pps', 'ppsx'],
        'output_formats': ['pdf'],
        'icon': '📊'
    },
    'images': {
        'name': 'Изображения',
        'input_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'],
        'output_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp'],
        'icon': '🖼️'
    }
}

# Расширения файлов и их описания
FILE_TYPE_INFO = {
    'docx': {'name': 'Word Document', 'icon': '📝'},
    'doc': {'name': 'Word Document (Old)', 'icon': '📝'},
    'pdf': {'name': 'PDF Document', 'icon': '📄'},
    'pptx': {'name': 'PowerPoint Presentation', 'icon': '📊'},
    'ppt': {'name': 'PowerPoint Presentation (Old)', 'icon': '📊'},
    'pps': {'name': 'PowerPoint Slideshow', 'icon': '📊'},
    'ppsx': {'name': 'PowerPoint Slideshow', 'icon': '📊'},
    'png': {'name': 'PNG Image', 'icon': '🖼️'},
    'jpg': {'name': 'JPEG Image', 'icon': '🖼️'},
    'jpeg': {'name': 'JPEG Image', 'icon': '🖼️'},
    'webp': {'name': 'WebP Image', 'icon': '🖼️'},
    'bmp': {'name': 'BMP Image', 'icon': '🖼️'},
    'gif': {'name': 'GIF Image', 'icon': '🖼️'},
    'tiff': {'name': 'TIFF Image', 'icon': '🖼️'},
}


def get_output_formats_for_input(input_format: str) -> list:
    """Возвращает возможные выходные форматы для входного"""
    return sorted([
        out_fmt for in_fmt, out_fmt in SUPPORTED_CONVERSIONS.keys()
        if in_fmt == input_format
    ])


def get_input_formats_for_output(output_format: str) -> list:
    """Возвращает возможные входные форматы для выходного"""
    return sorted([
        in_fmt for in_fmt, out_fmt in SUPPORTED_CONVERSIONS.keys()
        if out_fmt == output_format
    ])


def can_convert(input_format: str, output_format: str) -> bool:
    """Проверяет, возможна ли конвертация"""
    return (input_format, output_format) in SUPPORTED_CONVERSIONS


def get_converter_class(input_format: str, output_format: str) -> str:
    """Возвращает имя класса конвертера для указанных форматов"""
    return SUPPORTED_CONVERSIONS.get((input_format, output_format))