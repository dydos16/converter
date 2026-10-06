"""
Конвертер текстовых документов (odt, rtf, txt) через LibreOffice; TXT → DOCX — сами.
TXT бывает в UTF-8 или в Windows-1251 (старый Блокнот): кодировку определяем сами — LibreOffice угадывает её плохо.
"""
import re
import tempfile
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class TextDocumentConverter(BaseConverter):
    """Конвертер текстовых документов через LibreOffice и python-docx"""

    def get_input_formats(self):
        return ['odt', 'rtf', 'txt']

    def get_output_formats(self):
        return ['docx', 'pdf', 'txt', 'odt', 'rtf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        from src.core.libreoffice_manager import LibreOfficeManager, LO_MISSING
        from src.utils.helpers import read_text_any
        try:
            is_txt = input_path.suffix.lower() == '.txt'
            if is_txt and output_path.suffix.lower() == '.docx':
                return self._txt_to_docx(read_text_any(input_path), output_path)

            lo = LibreOfficeManager()
            if not lo.is_available():
                self._handle_error(LO_MISSING)
                return False
            self._update_status("Конвертация через LibreOffice...")
            if not is_txt:
                return lo.convert(input_path, output_path)
            # TXT отдаём LibreOffice уже в UTF-8 и говорим ему об этом прямо
            with tempfile.TemporaryDirectory() as tmp:
                utf8 = Path(tmp) / input_path.name
                utf8.write_text(read_text_any(input_path), encoding='utf-8')
                return lo.convert(utf8, output_path, infilter='Text (encoded):UTF8')

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации документа")
            return False

    def _txt_to_docx(self, text: str, output_path: Path) -> bool:
        from docx import Document

        self._update_status("Создание DOCX документа...")
        # Коды цветов терминала (логи) и прочие управляющие символы Word хранить не умеет — убираем
        text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        doc = Document()
        for line in text.splitlines():
            doc.add_paragraph(line)
        doc.save(str(output_path))
        self._update_progress(100)
        self._update_status("Конвертация завершена!")
        return True
