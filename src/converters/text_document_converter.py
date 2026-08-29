"""
Конвертер текстовых документов (odt, rtf, txt)
"""
import sys
import subprocess
from pathlib import Path
from .base import BaseConverter
from loguru import logger


class TextDocumentConverter(BaseConverter):
    """Конвертер текстовых документов через LibreOffice и python-docx"""

    def __init__(self):
        super().__init__()
        self._soffice_path = None
        self.libreoffice_available = self._check_libreoffice()
        self.doc_available = self._check_python_docx()

    def _check_libreoffice(self):
        """Проверяет наличие LibreOffice"""
        import shutil
        import platform

        for name in ['libreoffice', 'soffice']:
            path = shutil.which(name)
            if path:
                self._soffice_path = Path(path)
                return True

        system = platform.system().lower()
        project_root = Path(__file__).parent.parent.parent
        from src.utils.helpers import get_libreoffice_dir
        app_support = get_libreoffice_dir()

        if system == 'darwin':
            paths = [
                app_support / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
                project_root / "resources" / "libreoffice" / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
                '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            ]
            for path in paths:
                if Path(path).exists():
                    self._soffice_path = path
                    return True
        elif system == 'windows':
            paths = [
                app_support / "windows" / "LibreOffice" / "program" / "soffice.exe",
                project_root / "resources" / "libreoffice" / "windows" / "LibreOffice" / "program" / "soffice.exe",
                'C:/Program Files/LibreOffice/program/soffice.exe',
            ]
            for path in paths:
                if Path(path).exists():
                    self._soffice_path = path
                    return True
        else:
            if Path('/usr/bin/libreoffice').exists():
                self._soffice_path = Path('/usr/bin/libreoffice')
                return True

        return False

    def _check_python_docx(self):
        """Проверяет наличие python-docx"""
        try:
            import docx
            return True
        except ImportError:
            return False

    def _install_python_docx(self):
        """Устанавливает python-docx"""
        try:
            self._update_status("Установка python-docx...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'python-docx', '--quiet'
            ])
            self.doc_available = True
            return True
        except Exception as e:
            logger.error(f"Ошибка установки python-docx: {e}")
            return False

    def get_input_formats(self):
        return ['odt', 'rtf', 'txt']

    def get_output_formats(self):
        return ['docx', 'pdf', 'txt', 'odt', 'rtf']

    def convert(self, input_path: Path, output_path: Path) -> bool:
        try:
            input_ext = input_path.suffix.lower().lstrip('.')
            output_ext = output_path.suffix.lower().lstrip('.')

            # Если есть LibreOffice, используем его для всех форматов
            if self.libreoffice_available:
                return self._convert_with_libreoffice(input_path, output_path, output_ext)

            # Если нет LibreOffice, пробуем простые конвертации
            if output_ext == 'txt':
                return self._convert_to_text(input_path, output_path)
            elif output_ext == 'docx' and input_ext == 'txt':
                return self._txt_to_docx(input_path, output_path)

            self._handle_error(
                f"LibreOffice не найден!\n\n"
                f"Для конвертации {input_ext} -> {output_ext} необходим LibreOffice:\n"
                f"- macOS: brew install --cask libreoffice\n"
                f"- Windows: https://www.libreoffice.org/download/\n"
                f"- Linux: sudo apt install libreoffice"
            )
            return False

        except Exception as e:
            self._handle_error(f"Ошибка: {str(e)}")
            logger.exception("Ошибка конвертации документа")
            return False

    def _user_installation_arg(self) -> str:
        """Возвращает аргумент -env:UserInstallation для изолированного профиля LibreOffice."""
        try:
            from src.core.libreoffice_manager import LibreOfficeManager
            return LibreOfficeManager()._get_user_profile_path().replace('file://', '-env:UserInstallation=file://')
        except Exception:
            return '--norestore'

    def _convert_with_libreoffice(self, input_path: Path, output_path: Path, output_ext: str) -> bool:
        """Конвертирует через LibreOffice"""
        self._update_status(f"Конвертация через LibreOffice...")

        # Определяем фильтр для LibreOffice
        filters = {
            'docx': 'docx',
            'pdf': 'pdf',
            'txt': 'txt',
            'odt': 'odt',
            'rtf': 'rtf'
        }

        filter_name = filters.get(output_ext, output_ext)

        cmd = [
            str(self._soffice_path),
            self._user_installation_arg(),
            '--headless',
            '--invisible',
            '--nocrashreport',
            '--nofirststartwizard',
            '--nologo',
            '--norestore',
            '--convert-to', filter_name,
            '--outdir', str(output_path.parent),
            str(input_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            expected_file = output_path.parent / f"{input_path.stem}.{output_ext}"
            if expected_file.exists():
                if expected_file != output_path:
                    expected_file.rename(output_path)
                self._update_progress(100)
                self._update_status("Конвертация завершена!")
                return True

            # Ищем любой файл
            for file in output_path.parent.glob(f"{input_path.stem}*.{output_ext}"):
                if file != output_path:
                    file.rename(output_path)
                    self._update_progress(100)
                    self._update_status("Конвертация завершена!")
                    return True

            return False

        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return False

    def _convert_to_text(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует в простой текст"""
        try:
            input_ext = input_path.suffix.lower().lstrip('.')

            if input_ext == 'txt':
                # Просто копируем
                import shutil
                shutil.copy2(input_path, output_path)
                return True

            # Пробуем извлечь текст из odt или rtf
            if input_ext == 'odt':
                # odt - это zip архив с xml
                import zipfile
                import xml.etree.ElementTree as ET

                with zipfile.ZipFile(input_path, 'r') as zipf:
                    with zipf.open('content.xml') as content:
                        tree = ET.parse(content)
                        root = tree.getroot()

                        # Извлекаем текст из всех текстовых узлов
                        text_content = []
                        for elem in root.iter():
                            if elem.text:
                                text_content.append(elem.text)

                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(text_content))
                        return True

            elif input_ext == 'rtf':
                # Простое извлечение текста из RTF
                with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Удаляем RTF команды
                import re
                text = re.sub(r'\\[a-z]+', '', content)
                text = re.sub(r'\{.*?\}', '', text)
                text = re.sub(r'\\[0-9]+', '', text)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return False

    def _txt_to_docx(self, input_path: Path, output_path: Path) -> bool:
        """Конвертирует TXT в DOCX"""
        if not self.doc_available:
            if not self._install_python_docx():
                return False

        try:
            from docx import Document

            self._update_status("Создание DOCX документа...")

            doc = Document()

            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    doc.add_paragraph(line.strip())

            doc.save(str(output_path))

            self._update_progress(100)
            self._update_status("Конвертация завершена!")
            return True

        except Exception as e:
            logger.error(f"Ошибка создания DOCX: {e}")
            return False