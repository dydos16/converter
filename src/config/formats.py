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

    # Изображения - ВСЕ КОМБИНАЦИИ
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

    # ============ PDF КОНВЕРТАЦИИ ============

    # PDF в документы
    ('pdf', 'docx'): 'PdfToDocxConverter',
    ('pdf', 'doc'): 'PdfToDocxConverter',
    ('pdf', 'odt'): 'PdfToDocxConverter',
    ('pdf', 'rtf'): 'PdfToDocxConverter',
    ('pdf', 'txt'): 'PdfToTextConverter',

    # PDF в презентации
    ('pdf', 'pptx'): 'PdfToPptxConverter',
    ('pdf', 'ppt'): 'PdfToPptxConverter',
    ('pdf', 'odp'): 'PdfToPptxConverter',

    # PDF в изображения
    ('pdf', 'png'): 'PdfToImageConverter',
    ('pdf', 'jpg'): 'PdfToImageConverter',
    ('pdf', 'jpeg'): 'PdfToImageConverter',
    ('pdf', 'webp'): 'PdfToImageConverter',
    ('pdf', 'bmp'): 'PdfToImageConverter',
    ('pdf', 'gif'): 'PdfToImageConverter',
    ('pdf', 'tiff'): 'PdfToImageConverter',

    # PDF в таблицы
    ('pdf', 'xlsx'): 'PdfToSpreadsheetConverter',
    ('pdf', 'xls'): 'PdfToSpreadsheetConverter',
    ('pdf', 'csv'): 'PdfToSpreadsheetConverter',

    # PDF в HTML
    ('pdf', 'html'): 'PdfToHtmlConverter',

    # PDF в JSON
    ('pdf', 'json'): 'PdfToJsonConverter',

    # PDF в XML
    ('pdf', 'xml'): 'PdfToXmlConverter',

    # PDF в Markdown
    ('pdf', 'md'): 'PdfToMarkdownConverter',

    # Сжатие PDF (PDF -> PDF)
    ('pdf', 'pdf'): 'PdfCompressor',

    # ============ ОСТАЛЬНЫЕ КОНВЕРТАЦИИ ============

    # Таблицы (Excel, CSV)
    ('xlsx', 'pdf'): 'SpreadsheetConverter',
    ('xlsx', 'csv'): 'SpreadsheetConverter',
    ('xlsx', 'xls'): 'SpreadsheetConverter',
    ('xls', 'pdf'): 'SpreadsheetConverter',
    ('xls', 'csv'): 'SpreadsheetConverter',
    ('xls', 'xlsx'): 'SpreadsheetConverter',
    ('csv', 'pdf'): 'SpreadsheetConverter',
    ('csv', 'xlsx'): 'SpreadsheetConverter',
    ('csv', 'xls'): 'SpreadsheetConverter',

    # Текстовые документы
    ('odt', 'docx'): 'TextDocumentConverter',
    ('odt', 'pdf'): 'TextDocumentConverter',
    ('odt', 'txt'): 'TextDocumentConverter',
    ('odt', 'rtf'): 'TextDocumentConverter',
    ('rtf', 'docx'): 'TextDocumentConverter',
    ('rtf', 'pdf'): 'TextDocumentConverter',
    ('rtf', 'txt'): 'TextDocumentConverter',
    ('txt', 'docx'): 'TextDocumentConverter',
    ('txt', 'pdf'): 'TextDocumentConverter',

    # HEIC изображения (iPhone)
    ('heic', 'jpg'): 'HeicConverter',
    ('heic', 'jpeg'): 'HeicConverter',
    ('heic', 'png'): 'HeicConverter',
    ('heic', 'webp'): 'HeicConverter',
    ('heif', 'jpg'): 'HeicConverter',
    ('heif', 'jpeg'): 'HeicConverter',
    ('heif', 'png'): 'HeicConverter',
    ('heif', 'webp'): 'HeicConverter',
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
        'input_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff', 'heic', 'heif'],
        'output_formats': ['png', 'jpg', 'jpeg', 'webp', 'bmp'],
        'icon': '🖼️'
    },
    'pdf': {
        'name': 'PDF документы',
        'input_formats': ['pdf'],
        'output_formats': [
            'docx', 'doc', 'odt', 'rtf', 'txt',           # Документы
            'pptx', 'ppt', 'odp',                          # Презентации
            'png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff',  # Изображения
            'xlsx', 'xls', 'csv',                          # Таблицы
            'html', 'json', 'xml', 'md',                   # Веб и данные
            'pdf'                                          # Сжатие
        ],
        'icon': '📑'
    },
    'spreadsheets': {
        'name': 'Таблицы',
        'input_formats': ['xlsx', 'xls', 'csv'],
        'output_formats': ['xlsx', 'xls', 'csv', 'pdf'],
        'icon': '📊'
    },
    'text_documents': {
        'name': 'Текстовые документы',
        'input_formats': ['odt', 'rtf', 'txt'],
        'output_formats': ['docx', 'pdf', 'txt', 'odt', 'rtf'],
        'icon': '📝'
    }
}

# Расширения файлов и их описания
FILE_TYPE_INFO = {
    'docx': {'name': 'Word Document', 'icon': '📝'},
    'doc': {'name': 'Word Document (Old)', 'icon': '📝'},
    'odt': {'name': 'OpenDocument Text', 'icon': '📝'},
    'rtf': {'name': 'Rich Text Format', 'icon': '📝'},
    'txt': {'name': 'Text File', 'icon': '📝'},
    'pdf': {'name': 'PDF Document', 'icon': '📄'},
    'pptx': {'name': 'PowerPoint Presentation', 'icon': '📊'},
    'ppt': {'name': 'PowerPoint Presentation (Old)', 'icon': '📊'},
    'odp': {'name': 'OpenDocument Presentation', 'icon': '📊'},
    'pps': {'name': 'PowerPoint Slideshow', 'icon': '📊'},
    'ppsx': {'name': 'PowerPoint Slideshow', 'icon': '📊'},
    'png': {'name': 'PNG Image', 'icon': '🖼️'},
    'jpg': {'name': 'JPEG Image', 'icon': '🖼️'},
    'jpeg': {'name': 'JPEG Image', 'icon': '🖼️'},
    'webp': {'name': 'WebP Image', 'icon': '🖼️'},
    'bmp': {'name': 'BMP Image', 'icon': '🖼️'},
    'gif': {'name': 'GIF Image', 'icon': '🖼️'},
    'tiff': {'name': 'TIFF Image', 'icon': '🖼️'},
    'heic': {'name': 'HEIC Image (iPhone)', 'icon': '🖼️'},
    'heif': {'name': 'HEIF Image', 'icon': '🖼️'},
    'xlsx': {'name': 'Excel Workbook', 'icon': '📊'},
    'xls': {'name': 'Excel Workbook (Old)', 'icon': '📊'},
    'csv': {'name': 'CSV File', 'icon': '📊'},
    'html': {'name': 'HTML Web Page', 'icon': '🌐'},
    'json': {'name': 'JSON Data', 'icon': '📋'},
    'xml': {'name': 'XML Data', 'icon': '📋'},
    'md': {'name': 'Markdown', 'icon': '📝'},
}


def get_output_formats_for_input(input_format: str) -> list:
    """Возвращает возможные выходные форматы для входного"""
    return sorted([
        out_fmt for in_fmt, out_fmt in SUPPORTED_CONVERSIONS.keys()
        if in_fmt == input_format.lower().lstrip('.')
    ])


def get_input_formats_for_output(output_format: str) -> list:
    """Возвращает возможные входные форматы для выходного"""
    return sorted([
        in_fmt for in_fmt, out_fmt in SUPPORTED_CONVERSIONS.keys()
        if out_fmt == output_format.lower().lstrip('.')
    ])


def can_convert(input_format: str, output_format: str) -> bool:
    """Проверяет, возможна ли конвертация"""
    return (input_format.lower().lstrip('.'), output_format.lower().lstrip('.')) in SUPPORTED_CONVERSIONS


def get_converter_class(input_format: str, output_format: str) -> str:
    """Возвращает имя класса конвертера для указанных форматов"""
    return SUPPORTED_CONVERSIONS.get((input_format.lower().lstrip('.'), output_format.lower().lstrip('.')))