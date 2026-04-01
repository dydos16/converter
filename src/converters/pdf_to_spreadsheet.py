"""
PDF to Spreadsheet - извлечение таблиц из PDF
"""
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToSpreadsheetConverter(BaseConverter):
    """Конвертер PDF в таблицы через pdfplumber"""

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Извлечение таблиц из PDF...")
            self._update_progress(10)

            try:
                import pdfplumber
                import pandas as pd

                self._update_status("Анализ PDF...")
                self._update_progress(30)

                all_tables = []

                with pdfplumber.open(str(input_path)) as pdf:
                    total_pages = len(pdf.pages)

                    for page_num, page in enumerate(pdf.pages):
                        self._update_progress(30 + int((page_num / total_pages) * 50))

                        # Извлекаем таблицы со страницы
                        tables = page.extract_tables()

                        if tables:
                            for table in tables:
                                if table and len(table) > 1:  # Игнорируем пустые таблицы
                                    # Очищаем таблицу от пустых строк
                                    cleaned_table = [row for row in table if any(cell and str(cell).strip() for cell in row)]
                                    if cleaned_table:
                                        all_tables.append(cleaned_table)
                                        self._update_status(f"Найдена таблица на странице {page_num + 1}")

                if not all_tables:
                    self._update_status("Таблицы не найдены, извлекаем текст...")
                    return self._extract_text_fallback(input_path, output_path)

                self._update_progress(80)

                output_ext = output_path.suffix.lower().lstrip('.')

                # Объединяем все таблицы
                if len(all_tables) == 1:
                    # Одна таблица
                    df = pd.DataFrame(all_tables[0])
                else:
                    # Несколько таблиц - объединяем с разделителями
                    dfs = []
                    for i, table in enumerate(all_tables):
                        # Добавляем заголовок
                        header_df = pd.DataFrame([[f"=== Table {i+1} ==="]], columns=[''])
                        dfs.append(header_df)

                        # Добавляем саму таблицу
                        df_table = pd.DataFrame(table)
                        dfs.append(df_table)

                        # Добавляем пустую строку
                        dfs.append(pd.DataFrame([['']]))

                    df = pd.concat(dfs, ignore_index=True)

                # Сохраняем
                if output_ext in ['xlsx', 'xls']:
                    df.to_excel(str(output_path), index=False, header=False)
                elif output_ext == 'csv':
                    df.to_csv(str(output_path), index=False, header=False, encoding='utf-8')

                self._update_progress(100)
                self._update_status(f"Извлечено {len(all_tables)} таблиц")
                return True

            except ImportError:
                self._handle_error(
                    "Установите необходимые библиотеки:\n\n"
                    "pip install --break-system-packages pdfplumber pandas openpyxl\n\n"
                    "Или используйте виртуальное окружение:\n"
                    "python3 -m venv venv\n"
                    "source venv/bin/activate\n"
                    "pip install pdfplumber pandas openpyxl"
                )
                return False

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка извлечения таблиц из PDF")
            return False

    def _extract_text_fallback(self, input_path: Path, output_path: Path) -> bool:
        """Запасной вариант - извлечение текста"""
        try:
            import pdfplumber
            import pandas as pd

            self._update_status("Извлечение текста...")

            all_text = []

            with pdfplumber.open(str(input_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        all_text.append(f"=== Page {page_num + 1} ===")
                        all_text.append(text)
                        all_text.append("")

            lines = []
            for line in '\n'.join(all_text).split('\n'):
                if line.strip():
                    lines.append(line.strip())

            df = pd.DataFrame(lines, columns=['Content'])

            output_ext = output_path.suffix.lower().lstrip('.')

            if output_ext in ['xlsx', 'xls']:
                df.to_excel(str(output_path), index=False)
            elif output_ext == 'csv':
                df.to_csv(str(output_path), index=False, encoding='utf-8')

            self._update_progress(100)
            self._update_status("Текст успешно извлечен")
            return True

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return False