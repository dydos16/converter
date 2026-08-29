"""
Единые утилиты для работы с LibreOffice
"""
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger


class LibreOfficeUtils:
    """Единый класс для работы с LibreOffice"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self._soffice_path: Optional[Path] = None
        self._cached_available: Optional[bool] = None
    
    def find_soffice(self) -> Optional[Path]:
        """Находит путь к LibreOffice"""
        if self._soffice_path:
            return self._soffice_path
        
        # 1. PATH
        for name in ['libreoffice', 'soffice']:
            path = shutil.which(name)
            if path:
                self._soffice_path = Path(path)
                return self._soffice_path
        
        # 2. App Support (встроенный / самодостаточный LibreOffice)
        from src.utils.helpers import get_libreoffice_dir
        app_support = get_libreoffice_dir()
        if self.system == 'darwin':
            lo_app = app_support / "macos" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice"
        elif self.system == 'windows':
            lo_app = app_support / "windows" / "LibreOffice" / "program" / "soffice.exe"
        else:
            lo_app = app_support / "linux" / "usr" / "bin" / "soffice"
        
        if lo_app.exists():
            self._soffice_path = lo_app
            return self._soffice_path
        
        # 3. Системные пути
        if self.system == 'darwin':
            for p in [
                Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                Path('/opt/homebrew/bin/soffice'),
            ]:
                if p.exists():
                    self._soffice_path = p
                    return self._soffice_path
        
        elif self.system == 'windows':
            for p in [
                Path('C:/Program Files/LibreOffice/program/soffice.exe'),
                Path('C:/Program Files (x86)/LibreOffice/program/soffice.exe'),
            ]:
                if p.exists():
                    self._soffice_path = p
                    return self._soffice_path
        
        return None
    
    def is_installed(self) -> bool:
        """Проверяет, работает ли LibreOffice"""
        if self._cached_available is not None:
            return self._cached_available
        
        soffice = self.find_soffice()
        if not soffice:
            self._cached_available = False
            return False
        
        try:
            result = subprocess.run(
                [str(soffice), '--version'],
                capture_output=True,
                timeout=10
            )
            self._cached_available = result.returncode == 0
            if self._cached_available:
                logger.info(f"LibreOffice готов: {result.stdout.decode('utf-8', errors='ignore').strip()[:50]}")
            return self._cached_available
        except Exception as e:
            logger.warning(f"LibreOffice не отвечает: {e}")
            self._cached_available = False
            return False
    
    def get_install_instructions(self) -> str:
        """Инструкция по установке"""
        if self.system == 'darwin':
            return "❌ LibreOffice не найден!\n\n📥 brew install --cask libreoffice"
        elif self.system == 'windows':
            return "❌ LibreOffice не найден!\n\n📥 https://www.libreoffice.org/download/"
        else:
            return "❌ LibreOffice не найден!\n\n📥 sudo apt install libreoffice"
    
    def _get_startupinfo(self):
        """Возвращает startupinfo для Windows (скрыть окно)"""
        if self.system == 'windows':
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = subprocess.SW_HIDE
            return info
        return None
    
    def convert_to_pdf(
        self, 
        input_path: Path, 
        output_path: Path, 
        progress_callback=None
    ) -> bool:
        """Конвертирует в PDF через LibreOffice"""
        if not self.is_installed():
            return False
        
        cmd = [
            str(self._soffice_path),
            '--headless', '--invisible', '--nocrashreport',
            '--nofirststartwizard', '--nologo', '--norestore',
            '--convert-to', 'pdf',
            '--outdir', str(output_path.parent),
            str(input_path)
        ]
        
        logger.debug(f"LibreOffice: {' '.join(cmd)}")
        
        try:
            if progress_callback:
                progress_callback(50)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                startupinfo=self._get_startupinfo()
            )
            
            if progress_callback:
                progress_callback(80)
            
            expected_pdf = output_path.parent / f"{input_path.stem}.pdf"
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                return True
            
            for f in output_path.parent.glob(f"{input_path.stem}*.pdf"):
                if f != output_path:
                    f.rename(output_path)
                    if progress_callback:
                        progress_callback(100)
                    return True
            
            logger.error(f"PDF не создан: {result.stderr[:200]}")
            return False
            
        except subprocess.TimeoutExpired:
            logger.error("Таймаут LibreOffice")
            return False
        except Exception as e:
            logger.exception(f"Ошибка: {e}")
            return False
    
    def convert_to_format(
        self,
        input_path: Path,
        output_path: Path,
        target_format: str,
        progress_callback=None
    ) -> bool:
        """Конвертирует в произвольный формат"""
        if not self.is_installed():
            return False
        
        cmd = [
            str(self._soffice_path),
            '--headless', '--invisible', '--nocrashreport',
            '--nofirststartwizard', '--nologo', '--norestore',
            '--convert-to', target_format,
            '--outdir', str(output_path.parent),
            str(input_path)
        ]
        
        try:
            if progress_callback:
                progress_callback(50)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                startupinfo=self._get_startupinfo()
            )
            
            expected = output_path.parent / f"{input_path.stem}.{target_format}"
            if expected.exists():
                if expected != output_path:
                    expected.rename(output_path)
                if progress_callback:
                    progress_callback(100)
                return True
            
            return False
        except Exception as e:
            logger.exception(f"Ошибка: {e}")
            return False
