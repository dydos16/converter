"""
PDF to PPTX: страница — слайд. Фон — страница без текста (картинки, линии таблиц, заливки), поверх — настоящие
надписи PowerPoint на тех же местах: их можно править. Скан (без текста) — слайд-картинка.
"""
import re
import tempfile
from pathlib import Path
from .base import BaseConverter
from .pdf_text import block_lines, has_text, line_pieces, line_segments
from loguru import logger

EMU_PER_PT = 12700                  # единицы PowerPoint в одном типографском пункте
MAX_SLIDE_PT = 56 * 72              # PowerPoint не принимает слайды больше 56 дюймов
BOLD, ITALIC = 16, 2                # флаги шрифта в PyMuPDF


def font_family(pdf_font: str) -> str:
    """«ABCDEF+TimesNewRomanPSMT-Bold» → «Times New Roman»: семейство без подмножества и начертания."""
    name = re.split(r"[-,]", re.sub(r"^[A-Z]{6}\+", "", pdf_font))[0]
    name = re.sub(r"(PSMT|MT|PS)$", "", name)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


class PdfToPptxConverter(BaseConverter):
    """Конвертер PDF в PPTX: слайд на страницу, текст редактируемый"""

    def __init__(self):
        super().__init__()
        self.dpi = 150
        self.quality = 85

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['pptx', 'ppt', 'odp']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        # ppt/odp писать сами не умеем: делаем PPTX и пересохраняем через LibreOffice
        if output_path.suffix.lower() != '.pptx':
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager().convert_via(lambda pptx: self.convert(input_path, pptx), output_path, '.pptx')
        try:
            import fitz
            from pptx import Presentation

            self._update_status("Чтение PDF...")
            self._update_progress(10)

            # Второй экземпляр документа — для фона: из него вырезаем текст
            with fitz.open(input_path) as doc, fitz.open(input_path) as bare, tempfile.TemporaryDirectory() as tmp:
                total_pages = len(doc)
                prs = Presentation()
                # Слайд — по пропорциям первой страницы, иначе A4 растягивается в 16:9
                first = doc[0].rect
                k = min(1.0, MAX_SLIDE_PT / max(first.width, first.height))
                prs.slide_width = int(first.width * k * EMU_PER_PT)
                prs.slide_height = int(first.height * k * EMU_PER_PT)

                for i, page in enumerate(doc):
                    self._update_progress(10 + int(i / total_pages * 85))
                    self._update_status(f"Слайд {i + 1}/{total_pages}")
                    # Страница целиком и без искажений: вписываем по центру, сохраняя пропорции
                    scale = min(prs.slide_width / page.rect.width, prs.slide_height / page.rect.height)
                    ox = (prs.slide_width - page.rect.width * scale) / 2
                    oy = (prs.slide_height - page.rect.height * scale) / 2

                    # Повёрнутая страница (/Rotate) — целиком картинкой, как скан: координаты текста у неё
                    # в неповёрнутой системе, и надписи легли бы мимо
                    editable = has_text(page) and not page.rotation
                    blocks = [b for b in page.get_text("rawdict")["blocks"] if b["type"] == 0] if editable else []
                    background = bare[i]
                    if blocks:
                        for block in blocks:
                            background.add_redact_annot(fitz.Rect(block["bbox"]), fill=False)
                        background.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                                    graphics=fitz.PDF_REDACT_LINE_ART_NONE)
                    png = Path(tmp) / f"{i}.png"
                    background.get_pixmap(dpi=self.dpi).save(png)

                    slide = prs.slides.add_slide(prs.slide_layouts[6])
                    slide.shapes.add_picture(str(png), int(ox), int(oy),
                                             int(page.rect.width * scale), int(page.rect.height * scale))
                    for block in blocks:
                        self._add_text_box(slide, block, scale, ox, oy)

                self._update_status("Сохранение презентации...")
                self._update_progress(95)
                prs.save(str(output_path))

            self._update_progress(100)
            self._update_status(f"Конвертация завершена! Создано {total_pages} слайдов")
            return True

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации PDF в PPTX")
            return False

    def _add_text_box(self, slide, block, scale, ox, oy):
        rows = block_lines(block)
        if any(len(line_segments(row)) > 1 for row in rows):
            # Таблица или колонки: каждая ячейка — своя надпись на своём месте
            for row in rows:
                top = min(span["bbox"][1] for span in row)
                bottom = max(span["bbox"][3] for span in row)
                for x0, x1, pieces in line_segments(row):
                    self._text_box(slide, [pieces], (x0, top, x1, bottom), scale, ox, oy)
        else:
            # Обычный текст — одна надпись на блок, удобно править
            self._text_box(slide, [line_pieces(row) for row in rows], block["bbox"], scale, ox, oy)

    @staticmethod
    def _text_box(slide, lines, bbox, scale, ox, oy):
        from pptx.dml.color import RGBColor
        from pptx.enum.text import MSO_AUTO_SIZE
        from pptx.util import Pt

        x0, y0, x1, y1 = bbox
        # Шире исходного: шрифт на чужом компьютере бывает шире, а переносить строки иначе, чем в PDF, нельзя
        box = slide.shapes.add_textbox(int(ox + x0 * scale), int(oy + y0 * scale),
                                       int((x1 - x0) * scale * 1.15) + 1, int((y1 - y0) * scale) + 1)
        frame = box.text_frame
        frame.word_wrap = False
        frame.auto_size = MSO_AUTO_SIZE.NONE
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        for j, pieces in enumerate(lines):
            paragraph = frame.paragraphs[0] if j == 0 else frame.add_paragraph()
            for text, span in pieces:
                run = paragraph.add_run()
                run.text = text
                if text.isspace():
                    continue
                font = span["font"].lower()
                run.font.size = Pt(round(span["size"] * scale / EMU_PER_PT * 2) / 2)
                run.font.bold = bool(span["flags"] & BOLD) or "bold" in font
                run.font.italic = bool(span["flags"] & ITALIC) or "italic" in font or "oblique" in font
                run.font.name = font_family(span["font"]) or None
                if span["color"]:
                    run.font.color.rgb = RGBColor.from_string(f"{span['color']:06X}")
