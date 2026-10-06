"""
PDF to DOCX через PyMuPDF: текст с оформлением (размер, жирный, курсив, цвет), таблицы Word и картинки —
в порядке сверху вниз, как на странице. Страница-скан попадает в документ картинкой.
"""
import io
from pathlib import Path
from .base import BaseConverter
from .pdf_text import block_lines, has_text, line_pieces, ocr_lines, page_text
from loguru import logger

BOLD, ITALIC = 16, 2        # флаги шрифта в PyMuPDF


class PdfToDocxConverter(BaseConverter):
    """Конвертер PDF в DOCX с сохранением форматирования"""

    def __init__(self):
        super().__init__()
        self.extract_text_only = False

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['docx', 'doc', 'odt', 'rtf']

    def set_extract_text_only(self, text_only: bool):
        """Только текст: без таблиц, картинок и оформления"""
        self.extract_text_only = text_only

    def convert(self, input_path: Path, output_path: Path) -> bool:
        # doc/odt/rtf писать сами не умеем: делаем DOCX и пересохраняем через LibreOffice
        if output_path.suffix.lower() != '.docx':
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager().convert_via(lambda docx: self.convert(input_path, docx), output_path, '.docx')
        try:
            import fitz
            from docx import Document
            from docx.shared import Pt

            self._update_status("Чтение PDF...")
            self._update_progress(10)
            doc = Document()
            with fitz.open(input_path) as pdf:
                # Размер листа — как у PDF (иначе A4 сверстается на американском Letter)
                section = doc.sections[0]
                section.page_width, section.page_height = Pt(pdf[0].rect.width), Pt(pdf[0].rect.height)
                for n, page in enumerate(pdf):
                    self._update_progress(10 + int(n / len(pdf) * 85))
                    self._update_status(f"Страница {n + 1} из {len(pdf)}")
                    if n:
                        doc.add_page_break()
                    self._add_page(doc, page)

            doc.save(str(output_path))
            self._update_progress(100)
            self._update_status("Конвертация PDF в DOCX завершена!")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка конвертации PDF в DOCX: {str(e)}")
            logger.exception("Ошибка конвертации PDF в DOCX")
            return False

    def _add_page(self, doc, page):
        import fitz
        from docx.shared import Pt

        if not has_text(page):
            # Скан: распознанный текст — абзацами; не распозналось — оставим страницу картинкой
            lines = ocr_lines(page)
            for _, pieces in lines:
                for text, span in pieces:
                    doc.add_paragraph().add_run(text).font.size = Pt(max(8, min(28, round(span["size"]))))
            if lines:
                return

        tables = [] if self.extract_text_only else page.find_tables().tables
        areas = [fitz.Rect(t.bbox) for t in tables]
        # Текст ячейки — по её области, теми же правилами, что и абзацы (иначе «Кол-во» распадается на куски)
        items = [(t.bbox[1], "table", [[page_text(page, clip=cell) if cell else "" for cell in row.cells]
                                       for row in t.rows]) for t in tables]
        for block in page.get_text("rawdict")["blocks"]:
            rect = fitz.Rect(block["bbox"])
            if any(((rect.tl + rect.br) / 2) in area for area in areas):
                continue                                # текст ячеек уже попадёт в таблицу
            if block["type"] == 0:
                items.append((rect.y0, "text", block))
            elif not self.extract_text_only:
                items.append((rect.y0, "image", block))

        section = doc.sections[-1]
        text_width = section.page_width - section.left_margin - section.right_margin
        for _, kind, data in sorted(items, key=lambda item: item[0]):
            if kind == "table":
                self._add_table(doc, data)
            elif kind == "image":
                self._add_image(doc, data, text_width)
            else:
                self._add_paragraph(doc, data)

    @staticmethod
    def _add_table(doc, rows):
        rows = [row for row in rows if row and any(cell for cell in row)]
        if not rows:
            return
        table = doc.add_table(rows=len(rows), cols=max(len(row) for row in rows))
        table.style = "Table Grid"
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.cell(r, c).text = (value or "").replace("\n", " ")

    @staticmethod
    def _add_image(doc, block, text_width):
        import fitz
        from docx.shared import Pt
        x0, _, x1, _ = block["bbox"]
        width = min(Pt(x1 - x0), text_width)            # ширина на странице, не больше полосы набора
        data = block["image"]
        try:
            doc.add_picture(io.BytesIO(data), width=width)
        except Exception:
            try:                                        # JPEG 2000 и прочее, чего Word не понимает, — в PNG
                doc.add_picture(io.BytesIO(fitz.Pixmap(data).tobytes("png")), width=width)
            except Exception as e:
                logger.warning(f"Картинку из PDF пропустили: {e}")

    def _add_paragraph(self, doc, block):
        from docx.shared import Pt, RGBColor
        paragraph = doc.add_paragraph()
        for i, row in enumerate(block_lines(block)):
            if i:
                paragraph.add_run(" ")                  # строки PDF — лишь визуальные переносы, абзац течёт
            for text, span in line_pieces(row):
                run = paragraph.add_run(text)
                if self.extract_text_only or text.isspace():
                    continue
                font = span["font"].lower()
                run.font.size = Pt(round(span["size"] * 2) / 2)
                run.bold = bool(span["flags"] & BOLD) or "bold" in font
                run.italic = bool(span["flags"] & ITALIC) or "italic" in font or "oblique" in font
                if span["color"]:
                    run.font.color.rgb = RGBColor.from_string(f"{span['color']:06X}")
