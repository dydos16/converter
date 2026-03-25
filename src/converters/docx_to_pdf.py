"""
Конвертер DOCX в PDF с гарантированными полосами в таблицах
"""
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table as ReportLabTable, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import re
from .base import BaseConverter
from loguru import logger


class DocxToPdfConverter(BaseConverter):

    def __init__(self):
        super().__init__()
        self.font_name = 'Helvetica'
        self.bold_font = 'Helvetica-Bold'
        self.italic_font = 'Helvetica-Oblique'
        self.bold_italic_font = 'Helvetica-BoldOblique'
        self.try_register_fonts()
        self.setup_styles()

    def try_register_fonts(self):
        """Пытается загрузить русские шрифты"""
        font_paths = [
            ('RussianFont', '/System/Library/Fonts/Supplemental/Arial.ttf'),
            ('RussianFontBold', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
            ('RussianFontItalic', '/System/Library/Fonts/Supplemental/Arial Italic.ttf'),
        ]

        for name, path in font_paths:
            if Path(path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    if name == 'RussianFont':
                        self.font_name = name
                    elif name == 'RussianFontBold':
                        self.bold_font = name
                    elif name == 'RussianFontItalic':
                        self.italic_font = name
                    logger.info(f"Загружен шрифт: {name}")
                except:
                    continue

    def setup_styles(self):
        """Настройка всех стилей"""
        # Обычный текст
        self.style_normal = ParagraphStyle(
            'Normal',
            fontName=self.font_name,
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            spaceBefore=0,
        )

        # Жирный текст
        self.style_bold = ParagraphStyle(
            'Bold',
            parent=self.style_normal,
            fontName=self.bold_font,
        )

        # Заголовок 1
        self.style_h1 = ParagraphStyle(
            'H1',
            fontName=self.bold_font,
            fontSize=16,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=12,
            spaceBefore=12,
            textColor=colors.HexColor('#1a5490'),
        )

        # Заголовок 2
        self.style_h2 = ParagraphStyle(
            'H2',
            fontName=self.bold_font,
            fontSize=13,
            leading=18,
            spaceAfter=10,
            spaceBefore=10,
            textColor=colors.HexColor('#2c3e50'),
        )

        # Заголовок 3
        self.style_h3 = ParagraphStyle(
            'H3',
            fontName=self.bold_font,
            fontSize=11,
            leading=16,
            spaceAfter=8,
            spaceBefore=8,
            textColor=colors.HexColor('#34495e'),
        )

        # Стиль для заголовков таблиц
        self.style_table_header = ParagraphStyle(
            'TableHeader',
            fontName=self.bold_font,
            fontSize=8,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.white,
        )

        # Стиль для ячеек таблиц
        self.style_table_cell = ParagraphStyle(
            'TableCell',
            fontName=self.font_name,
            fontSize=8,
            leading=12,
            alignment=TA_LEFT,
        )

    def get_input_formats(self):
        return ['docx', 'doc']

    def get_output_formats(self):
        return ['pdf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            logger.info(f"Конвертация: {input_path}")
            self._update_status("Чтение файла...")
            self._update_progress(20)

            doc = Document(input_path)

            self._update_status("Создание PDF...")
            self._update_progress(40)

            pdf = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=15*mm,
                leftMargin=15*mm,
                topMargin=20*mm,
                bottomMargin=20*mm,
            )

            story = []
            total = len(doc.paragraphs) + len(doc.tables)
            processed = 0

            for element in doc.element.body:
                if element.tag.endswith('p'):
                    for para in doc.paragraphs:
                        if para._element is element:
                            processed += 1
                            self._update_progress(40 + int((processed / max(total, 1)) * 50))
                            self.add_paragraph(para, story)
                            break

                elif element.tag.endswith('tbl'):
                    for table in doc.tables:
                        if table._element is element:
                            processed += 1
                            self._update_progress(40 + int((processed / max(total, 1)) * 50))
                            self.add_table(table, story)
                            break

            self._update_status("Сохранение...")
            self._update_progress(90)

            if story:
                pdf.build(story)
                logger.success(f"PDF создан: {output_path}")
            else:
                from reportlab.pdfgen import canvas
                c = canvas.Canvas(str(output_path), pagesize=A4)
                c.drawString(100, 500, "Нет содержимого")
                c.save()

            self._update_progress(100)
            self._update_status("Готово!")
            return True

        except Exception as e:
            self._handle_error(str(e))
            logger.exception("Ошибка конвертации")
            return False

    def add_paragraph(self, para, story):
        """Добавляет параграф с форматированием"""
        text = para.text.strip()

        if not text:
            story.append(Spacer(1, 3))
            return

        formatted_text = self.get_html_text(para)

        if not formatted_text:
            return

        style_name = para.style.name.lower() if para.style else ""
        style = self.style_normal

        if 'heading 1' in style_name or 'title' in style_name:
            style = self.style_h1
        elif 'heading 2' in style_name:
            style = self.style_h2
        elif 'heading 3' in style_name:
            style = self.style_h3
        elif text.isupper() and len(text) < 60 and ('ЗАДАЧА' in text or 'ТЕХНИЧЕСКОЕ' in text):
            style = self.style_h2
        elif text.startswith(('1.', '2.', '3.', '4.', '5.')) and '.' in text[:3]:
            style = self.style_h2
        elif re.match(r'^\d+\.\d+\.', text):
            style = self.style_h3

        if para.alignment:
            if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                style.alignment = TA_CENTER
            elif para.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
                style.alignment = TA_RIGHT
            elif para.alignment == WD_ALIGN_PARAGRAPH.LEFT:
                style.alignment = TA_LEFT
            else:
                style.alignment = TA_JUSTIFY

        try:
            story.append(Paragraph(formatted_text, style))
        except:
            safe_text = self.escape_xml(text[:500])
            story.append(Paragraph(safe_text, self.style_normal))

    def get_html_text(self, para):
        """Преобразует параграф в HTML с тегами форматирования"""
        if not para.runs:
            return self.escape_xml(para.text)

        result = []
        for run in para.runs:
            text = run.text
            if not text:
                continue

            text = self.escape_xml(text)

            if run.bold and run.italic:
                text = f'<b><i>{text}</i></b>'
            elif run.bold:
                text = f'<b>{text}</b>'
            elif run.italic:
                text = f'<i>{text}</i>'
            if run.underline:
                text = f'<u>{text}</u>'

            result.append(text)

        return ''.join(result)

    def add_paragraph(self, para, story):
        """Добавляет параграф с возможными полосами"""
        text = para.text.strip()

        if not text:
            story.append(Spacer(1, 3))
            return

        formatted_text = self.get_html_text(para)

        if not formatted_text:
            return

        # Определяем стиль
        style_name = para.style.name.lower() if para.style else ""
        style = self.style_normal

        if 'heading 1' in style_name or 'title' in style_name:
            style = self.style_h1
        elif 'heading 2' in style_name:
            style = self.style_h2
        elif 'heading 3' in style_name:
            style = self.style_h3
        elif text.isupper() and len(text) < 60 and ('ЗАДАЧА' in text or 'ТЕХНИЧЕСКОЕ' in text):
            style = self.style_h2
        elif text.startswith(('1.', '2.', '3.', '4.', '5.')) and '.' in text[:3]:
            style = self.style_h2
        elif re.match(r'^\d+\.\d+\.', text):
            style = self.style_h3

        # Добавляем параграф
        story.append(Paragraph(formatted_text, style))

    def add_table(self, table, story):
        """Добавляет таблицу с полосами"""
        if not table.rows:
            return

        story.append(Spacer(1, 8))

        # Получаем данные
        data = []
        num_cols = max(len(row.cells) for row in table.rows)
        page_width = A4[0] - 30*mm
        col_width = page_width / num_cols if num_cols > 0 else page_width

        for row_idx, row in enumerate(table.rows):
            row_data = []
            for cell in row.cells:
                cell_texts = []
                for cell_para in cell.paragraphs:
                    if cell_para.text.strip():
                        formatted = self.get_html_text(cell_para)
                        if formatted:
                            cell_texts.append(formatted)

                cell_content = '<br/>'.join(cell_texts) if cell_texts else ""

                if row_idx == 0:
                    style = self.style_table_header
                else:
                    style = self.style_table_cell

                row_data.append(Paragraph(cell_content, style))
            data.append(row_data)

        # Создаем таблицу
        if num_cols > 0:
            rl_table = ReportLabTable(data, colWidths=[col_width] * num_cols, repeatRows=1)
        else:
            rl_table = ReportLabTable(data)

        # Стиль таблицы с полосами
        table_style = TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#aaaaaa')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ])

        # Гарантированные полосы - чередование цветов для каждой строки
        for i in range(1, len(data)):
            if i % 2 == 1:  # Нечетные строки (1,3,5...)
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f0f0f0'))
            else:  # Четные строки (2,4,6...)
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.white)

        rl_table.setStyle(table_style)
        story.append(KeepTogether(rl_table))
        story.append(Spacer(1, 6))

    def escape_xml(self, text):
        """Экранирует XML спецсимволы"""
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))