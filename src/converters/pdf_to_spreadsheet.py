"""
PDF to Spreadsheet - улучшенное извлечение таблиц из PDF
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class PdfToSpreadsheetConverter(BaseConverter):
    """Конвертер PDF в таблицы с улучшенным распознаванием"""

    def __init__(self):
        super().__init__()
        self.camelot_available = self._check_camelot()
        self.tabula_available = self._check_tabula()
        self.pymupdf_available = self._check_pymupdf()
        self.table_strategy = 'auto'  # auto, lattice, stream

    def _check_camelot(self):
        try:
            import camelot
            return True
        except ImportError:
            return False

    def _check_tabula(self):
        try:
            import tabula
            return True
        except ImportError:
            return False

    def _check_pymupdf(self):
        try:
            import fitz
            return True
        except ImportError:
            return False

    def _install_packages(self):
        """Устанавливает все необходимые пакеты"""
        packages = []

        if not self.camelot_available:
            packages.append('camelot-py[cv]')
        if not self.tabula_available:
            packages.append('tabula-py')
        if not self.pymupdf_available:
            packages.append('PyMuPDF')

        if packages:
            self._update_status(f"Установка пакетов: {', '.join(packages)}...")
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', *packages, '--quiet'
                ])
                self.camelot_available = self._check_camelot()
                self.tabula_available = self._check_tabula()
                self.pymupdf_available = self._check_pymupdf()
                return True
            except Exception as e:
                logger.error(f"Ошибка установки: {e}")
                return False
        return True

    def set_table_strategy(self, strategy: str):
        """Устанавливает стратегию поиска таблиц: auto, lattice, stream"""
        self.table_strategy = strategy

    def get_input_formats(self):
        return ['pdf']

    def get_output_formats(self):
        return ['xlsx', 'xls', 'csv']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            self._update_status("Подготовка к извлечению таблиц...")
            self._update_progress(10)

            if not self._install_packages():
                self._handle_error(
                    "Не удалось установить необходимые библиотеки.\n\n"
                    "Попробуйте установить вручную:\n"
                    "pip install camelot-py[cv] tabula-py PyMuPDF pandas openpyxl"
                )
                return False

            output_ext = output_path.suffix.lower().lstrip('.')

            # Пробуем camelot (лучше для таблиц с линиями)
            if self.camelot_available:
                result = self._try_camelot(input_path, output_path, output_ext)
                if result:
                    return result

            # Пробуем tabula (лучше для таблиц без линий)
            if self.tabula_available:
                result = self._try_tabula(input_path, output_path, output_ext)
                if result:
                    return result

            # Если ничего не нашло, извлекаем текст
            self._update_status("Таблицы не найдены, извлекаем текст...")
            return self._extract_text_fallback(input_path, output_path, output_ext)

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка извлечения таблиц из PDF")
            return False

    def _try_camelot(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Пробует извлечь таблицы через camelot"""
        try:
            import camelot
            import pandas as pd

            self._update_status("Поиск таблиц (camelot)...")

            tables = []
            strategies = []

            if self.table_strategy == 'auto':
                strategies = ['lattice', 'stream']
            else:
                strategies = [self.table_strategy]

            for strategy in strategies:
                try:
                    self._update_status(f"Метод: {strategy}")
                    found = camelot.read_pdf(
                        str(input_path),
                        pages='all',
                        flavor=strategy,
                        line_scale=40 if strategy == 'lattice' else 15,
                        edge_tol=500 if strategy == 'stream' else 50,
                        split_text=True
                    )
                    if len(found) > 0:
                        tables.extend(found)
                        self._update_status(f"Найдено {len(found)} таблиц методом {strategy}")
                except Exception as e:
                    logger.debug(f"Ошибка {strategy}: {e}")
                    continue

            if len(tables) == 0:
                return False

            return self._save_tables(tables, output_path, output_ext, 'camelot')

        except Exception as e:
            logger.error(f"Ошибка camelot: {e}")
            return False

    def _try_tabula(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Пробует извлечь таблицы через tabula"""
        try:
            import tabula
            import pandas as pd

            self._update_status("Поиск таблиц (tabula)...")

            tables = []

            # Пробуем разные параметры
            params_list = [
                {'lattice': True, 'stream': False},   # С сеткой
                {'lattice': False, 'stream': True},   # Без сетки
                {'lattice': True, 'stream': True},    # Оба метода
            ]

            for params in params_list:
                try:
                    found = tabula.read_pdf(
                        str(input_path),
                        pages='all',
                        multiple_tables=True,
                        **params
                    )
                    if found and len(found) > 0:
                        tables.extend(found)
                        self._update_status(f"Найдено {len(found)} таблиц")
                except Exception as e:
                    continue

            if len(tables) == 0:
                return False

            return self._save_tables(tables, output_path, output_ext, 'tabula')

        except Exception as e:
            logger.error(f"Ошибка tabula: {e}")
            return False

    def _save_tables(self, tables, output_path: Path, output_ext: str, source: str) -> bool:
        """Сохраняет найденные таблицы"""
        try:
            import pandas as pd
            import openpyxl

            self._update_progress(60)
            self._update_status(f"Обработка {len(tables)} таблиц...")

            # Очищаем и форматируем таблицы
            cleaned_tables = []
            for i, table in enumerate(tables):
                if hasattr(table, 'df'):
                    df = table.df
                else:
                    df = table

                # Удаляем пустые строки и столбцы
                df = df.dropna(how='all')
                df = df.dropna(axis=1, how='all')

                # Заменяем NaN на пустые строки
                df = df.fillna('')

                # Добавляем заголовок таблицы
                header = pd.DataFrame([[f"=== Table {i+1} (from {source}) ==="]], columns=[''])
                cleaned_tables.append(header)
                cleaned_tables.append(df)
                cleaned_tables.append(pd.DataFrame([['']]))  # Пустая строка

            if len(cleaned_tables) == 0:
                return False

            # Объединяем все таблицы
            final_df = pd.concat(cleaned_tables, ignore_index=True)

            self._update_progress(80)

            # Сохраняем
            if output_ext in ['xlsx', 'xls']:
                final_df.to_excel(str(output_path), index=False, header=False, engine='openpyxl')
            elif output_ext == 'csv':
                final_df.to_csv(str(output_path), index=False, header=False, encoding='utf-8')

            self._update_progress(100)
            self._update_status(f"Успешно извлечено {len(tables)} таблиц")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            return False

    def _extract_text_fallback(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Запасной вариант - извлечение текста"""
        try:
            import fitz
            import pandas as pd

            self._update_status("Извлечение текста из PDF...")

            doc = fitz.open(str(input_path))

            all_text = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                all_text.append(f"=== Page {page_num + 1} ===")
                all_text.append(text)
                all_text.append("")

            doc.close()

            lines = []
            for line in '\n'.join(all_text).split('\n'):
                if line.strip():
                    lines.append(line.strip())

            df = pd.DataFrame(lines, columns=['Content'])

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