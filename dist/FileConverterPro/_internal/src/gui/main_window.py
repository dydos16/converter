"""
Главное окно приложения для PySide6
"""
import sys
from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel,
    QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QGroupBox, QCheckBox, QSpinBox, QSlider,
    QTabWidget, QTextEdit, QApplication, QMenu,
    QSplitter, QFrame, QGridLayout, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QAction

from src.converters.factory import ConverterFactory
from src.core.job_manager import JobManager, ConversionJob, JobStatus
from src.core.settings import Settings
from src.utils.helpers import get_file_size_str, get_unique_filename, ensure_output_directory
from loguru import logger


class ConversionWorker(QThread):
    """Поток для выполнения конвертации"""
    progress_updated = Signal(str, int)
    job_completed = Signal(str, bool, str)
    job_finished = Signal()

    def __init__(self, job_manager: JobManager):
        super().__init__()
        self.job_manager = job_manager

    def run(self):
        self.job_manager.start()
        self.exec()


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    # Сигналы для безопасного вызова из потоков
    show_info_signal = Signal(str, str)
    show_warning_signal = Signal(str, str)
    show_error_signal = Signal(str, str)

    # Сигналы для обновления UI из рабочих потоков
    update_file_item_signal = Signal(str, int)  # file_path, progress
    update_status_signal = Signal()

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.job_manager = JobManager(max_concurrent=self.settings.get('max_concurrent_jobs', 3))
        self.worker = ConversionWorker(self.job_manager)

        # Единый таймер для обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.setInterval(500)  # 500ms для плавности

        # Флаг для блокировки повторного запуска
        self.conversion_in_progress = False

        # Подключаем сигналы
        self.show_info_signal.connect(self._show_info_message)
        self.show_warning_signal.connect(self._show_warning_message)
        self.show_error_signal.connect(self._show_error_message)
        self.update_file_item_signal.connect(self._update_file_item_progress)
        self.update_status_signal.connect(self._update_status_forced)

        self.setup_ui()
        self.setup_callbacks()
        self.load_settings()

        self.worker.start()

    @Slot(str, str)
    def _show_info_message(self, title: str, message: str):
        """Безопасно показывает информационное сообщение"""
        QMessageBox.information(self, title, message)

    @Slot(str, str)
    def _show_warning_message(self, title: str, message: str):
        """Безопасно показывает предупреждение"""
        QMessageBox.warning(self, title, message)

    @Slot(str, str)
    def _show_error_message(self, title: str, message: str):
        """Безопасно показывает ошибку"""
        QMessageBox.critical(self, title, message)

    @Slot(str, int)
    def _update_file_item_progress(self, file_path: str, progress: int):
        """Обновляет прогресс в элементе списка (вызывается из сигнала)"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item_path = item.data(Qt.ItemDataRole.UserRole)
            if item_path == file_path:
                old_text = item.text()
                # Убираем старый прогресс если есть
                if ' (' in old_text and '%)' in old_text:
                    old_text = old_text.split(' (')[0]
                item.setText(f"{old_text} ({progress}%)")
                break

    @Slot()
    def _update_status_forced(self):
        """Принудительное обновление статуса"""
        self.update_status()

    def setup_ui(self):
        """Настраивает интерфейс"""
        self.setWindowTitle("File Converter Pro")
        self.setGeometry(100, 100, 1400, 900)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Создаем вкладки
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # Вкладка конвертации
        conversion_tab = QWidget()
        tabs.addTab(conversion_tab, "Конвертация")
        self.setup_conversion_tab(conversion_tab)

        # Вкладка настроек
        settings_tab = QWidget()
        tabs.addTab(settings_tab, "Настройки")
        self.setup_settings_tab(settings_tab)

        # Вкладка лога
        log_tab = QWidget()
        tabs.addTab(log_tab, "Лог")
        self.setup_log_tab(log_tab)

        # Статус бар
        self.status_label = QLabel("Готов к работе")
        self.statusBar().addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.statusBar().addPermanentWidget(self.progress_bar)

        self.active_jobs_label = QLabel("Активных: 0")
        self.statusBar().addPermanentWidget(self.active_jobs_label)

    def setup_conversion_tab(self, parent: QWidget):
        """Настраивает вкладку конвертации"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        # Верхняя панель
        top_panel = QHBoxLayout()

        # Выбор форматов
        format_group = QGroupBox("Форматы")
        format_layout = QHBoxLayout(format_group)

        self.input_format_combo = QComboBox()
        input_formats = ['Все'] + ConverterFactory.get_input_formats()
        self.input_format_combo.addItems(input_formats)
        self.input_format_combo.currentTextChanged.connect(self.on_input_format_changed)

        self.output_format_combo = QComboBox()
        self.output_format_combo.setEnabled(False)
        self.output_format_combo.currentTextChanged.connect(self.update_convert_button)

        format_layout.addWidget(QLabel("Из:"))
        format_layout.addWidget(self.input_format_combo)
        format_layout.addWidget(QLabel("В:"))
        format_layout.addWidget(self.output_format_combo)
        format_layout.addStretch()

        top_panel.addWidget(format_group)

        # Кнопки управления
        buttons_group = QGroupBox("Управление")
        buttons_layout = QHBoxLayout(buttons_group)

        self.add_files_btn = QPushButton("➕ Добавить файлы")
        self.add_files_btn.clicked.connect(self.add_files)

        self.add_folder_btn = QPushButton("📁 Добавить папку")
        self.add_folder_btn.clicked.connect(self.add_folder)

        self.clear_btn = QPushButton("🗑️ Очистить")
        self.clear_btn.clicked.connect(self.clear_files)

        self.convert_btn = QPushButton("🚀 Конвертировать")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        self.convert_btn.setMinimumHeight(40)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)

        buttons_layout.addWidget(self.add_files_btn)
        buttons_layout.addWidget(self.add_folder_btn)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.convert_btn)

        top_panel.addWidget(buttons_group)

        layout.addLayout(top_panel)

        # Список файлов
        file_group = QGroupBox("Файлы для конвертации")
        file_layout = QVBoxLayout(file_group)

        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(300)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        file_layout.addWidget(self.file_list)

        layout.addWidget(file_group)

        # Панель прогресса
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Общий прогресс:"))
        self.total_progress = QProgressBar()
        self.total_progress.setMinimumHeight(25)
        progress_layout.addWidget(self.total_progress)
        layout.addLayout(progress_layout)

        # Включаем Drag & Drop
        self.setAcceptDrops(True)

    def setup_settings_tab(self, parent: QWidget):
        """Настраивает вкладку настроек"""
        # Создаем скролл область
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        # Контейнер для содержимого
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Настройки изображений
        image_group = QGroupBox("Настройки изображений")
        image_layout = QVBoxLayout(image_group)

        # Качество
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Качество JPEG/WebP:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        quality_value = self.settings.get('image_quality', 85)
        if quality_value is None:
            quality_value = 85
        self.quality_slider.setValue(int(quality_value))
        self.quality_label = QLabel(f"{self.quality_slider.value()}%")
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_label.setText(f"{v}%")
        )
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        image_layout.addLayout(quality_layout)

        # Максимальный размер
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Макс. ширина:"))
        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(0, 10000)
        self.max_width_spin.setSpecialValueText("Без ограничений")
        width_value = self.settings.get('image_max_width', 0)
        if width_value is None:
            width_value = 0
        self.max_width_spin.setValue(int(width_value))

        size_layout.addWidget(self.max_width_spin)
        size_layout.addWidget(QLabel("Макс. высота:"))
        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(0, 10000)
        self.max_height_spin.setSpecialValueText("Без ограничений")
        height_value = self.settings.get('image_max_height', 0)
        if height_value is None:
            height_value = 0
        self.max_height_spin.setValue(int(height_value))

        image_layout.addLayout(size_layout)
        layout.addWidget(image_group)

        # Настройки PDF
        pdf_group = QGroupBox("Настройки PDF")
        pdf_layout = QVBoxLayout(pdf_group)

        # DPI для PDF
        dpi_layout = QHBoxLayout()
        dpi_layout.addWidget(QLabel("DPI (качество PDF → изображения):"))
        self.pdf_dpi_spin = QSpinBox()
        self.pdf_dpi_spin.setRange(72, 600)
        self.pdf_dpi_spin.setValue(self.settings.get('pdf_dpi', 200))
        self.pdf_dpi_spin.setSuffix(" DPI")
        dpi_layout.addWidget(self.pdf_dpi_spin)
        dpi_layout.addStretch()
        pdf_layout.addLayout(dpi_layout)

        # Качество для PDF в изображения
        pdf_quality_layout = QHBoxLayout()
        pdf_quality_layout.addWidget(QLabel("Качество изображений:"))
        self.pdf_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.pdf_quality_slider.setRange(1, 100)
        self.pdf_quality_slider.setValue(self.settings.get('pdf_quality', 85))
        self.pdf_quality_label = QLabel(f"{self.pdf_quality_slider.value()}%")
        self.pdf_quality_slider.valueChanged.connect(
            lambda v: self.pdf_quality_label.setText(f"{v}%")
        )
        pdf_quality_layout.addWidget(self.pdf_quality_slider)
        pdf_quality_layout.addWidget(self.pdf_quality_label)
        pdf_layout.addLayout(pdf_quality_layout)

        # Сжатие PDF
        compress_layout = QHBoxLayout()
        compress_layout.addWidget(QLabel("Уровень сжатия PDF:"))
        self.pdf_compress_spin = QSpinBox()
        self.pdf_compress_spin.setRange(0, 9)
        self.pdf_compress_spin.setValue(self.settings.get('pdf_compress_level', 6))
        self.pdf_compress_spin.setToolTip("0 - без сжатия, 9 - максимальное сжатие")
        compress_layout.addWidget(self.pdf_compress_spin)
        compress_layout.addStretch()
        pdf_layout.addLayout(compress_layout)

        # Чекбоксы для PDF
        self.pdf_remove_metadata_check = QCheckBox("Удалять метаданные")
        self.pdf_remove_metadata_check.setChecked(self.settings.get('pdf_remove_metadata', False))
        pdf_layout.addWidget(self.pdf_remove_metadata_check)

        self.pdf_optimize_images_check = QCheckBox("Оптимизировать изображения")
        self.pdf_optimize_images_check.setChecked(self.settings.get('pdf_optimize_images', True))
        pdf_layout.addWidget(self.pdf_optimize_images_check)

        # Стратегия извлечения таблиц
        table_strategy_layout = QHBoxLayout()
        table_strategy_layout.addWidget(QLabel("Стратегия извлечения таблиц:"))
        self.table_strategy_combo = QComboBox()
        self.table_strategy_combo.addItems(['auto', 'lattice', 'stream'])
        self.table_strategy_combo.setCurrentText(self.settings.get('pdf_table_strategy', 'auto'))
        self.table_strategy_combo.setToolTip(
            "auto - автоматический выбор\n"
            "lattice - для таблиц с сеткой\n"
            "stream - для таблиц без сетки"
        )
        table_strategy_layout.addWidget(self.table_strategy_combo)
        table_strategy_layout.addStretch()
        pdf_layout.addLayout(table_strategy_layout)

        layout.addWidget(pdf_group)

        # Настройки HEIC
        heic_group = QGroupBox("Настройки HEIC (iPhone фото)")
        heic_layout = QVBoxLayout(heic_group)

        heic_quality_layout = QHBoxLayout()
        heic_quality_layout.addWidget(QLabel("Качество:"))
        self.heic_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.heic_quality_slider.setRange(1, 100)
        self.heic_quality_slider.setValue(self.settings.get('heic_quality', 85))
        self.heic_quality_label = QLabel(f"{self.heic_quality_slider.value()}%")
        self.heic_quality_slider.valueChanged.connect(
            lambda v: self.heic_quality_label.setText(f"{v}%")
        )
        heic_quality_layout.addWidget(self.heic_quality_slider)
        heic_quality_layout.addWidget(self.heic_quality_label)
        heic_layout.addLayout(heic_quality_layout)

        layout.addWidget(heic_group)

        # Общие настройки
        general_group = QGroupBox("Общие настройки")
        general_layout = QVBoxLayout(general_group)

        self.auto_open_check = QCheckBox("Открывать папку после конвертации")
        auto_open = self.settings.get('auto_open_folder', True)
        self.auto_open_check.setChecked(auto_open if auto_open is not None else True)

        self.keep_name_check = QCheckBox("Сохранять оригинальное имя файла")
        keep_name = self.settings.get('keep_original_name', True)
        self.keep_name_check.setChecked(keep_name if keep_name is not None else True)

        self.notifications_check = QCheckBox("Показывать уведомления")
        show_notifications = self.settings.get('show_notifications', True)
        self.notifications_check.setChecked(show_notifications if show_notifications is not None else True)

        # Максимум одновременных задач
        max_jobs_layout = QHBoxLayout()
        max_jobs_layout.addWidget(QLabel("Максимум одновременных задач:"))
        self.max_jobs_spin = QSpinBox()
        self.max_jobs_spin.setRange(1, 10)
        self.max_jobs_spin.setValue(self.settings.get('max_concurrent_jobs', 3))

        # Обновляем менеджер при изменении
        self.max_jobs_spin.valueChanged.connect(self._update_max_concurrent)

        max_jobs_layout.addWidget(self.max_jobs_spin)
        max_jobs_layout.addStretch()
        general_layout.addLayout(max_jobs_layout)

        general_layout.addWidget(self.auto_open_check)
        general_layout.addWidget(self.keep_name_check)
        general_layout.addWidget(self.notifications_check)

        layout.addWidget(general_group)

        # Кнопка сохранения
        save_btn = QPushButton("💾 Сохранить настройки")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(40)
        layout.addWidget(save_btn)

        layout.addStretch()

        # Устанавливаем содержимое в скролл
        scroll.setWidget(content_widget)

        # Добавляем скролл в родительский виджет
        parent_layout = QVBoxLayout(parent)
        parent_layout.setContentsMargins(0, 0, 0, 0)
        parent_layout.addWidget(scroll)

    def setup_log_tab(self, parent: QWidget):
        """Настраивает вкладку лога"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 10))
        layout.addWidget(self.log_text)

        # Кнопки управления логом
        log_buttons_layout = QHBoxLayout()

        clear_log_btn = QPushButton("🗑️ Очистить лог")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_buttons_layout.addWidget(clear_log_btn)

        log_buttons_layout.addStretch()
        layout.addLayout(log_buttons_layout)

    def setup_callbacks(self):
        """Настраивает callback'и менеджера задач"""
        self.job_manager.register_callback('on_job_started', self.on_job_started)
        self.job_manager.register_callback('on_job_progress', self.on_job_progress)
        self.job_manager.register_callback('on_job_completed', self.on_job_completed)
        self.job_manager.register_callback('on_job_failed', self.on_job_failed)

    def load_settings(self):
        """Загружает настройки"""
        recent_formats = self.settings.get('recent_formats', [])
        if recent_formats:
            last_format = recent_formats[0]
            if '→' in last_format:
                inp, out = last_format.split('→')
                index = self.input_format_combo.findText(inp)
                if index >= 0:
                    self.input_format_combo.setCurrentIndex(index)

    def save_settings(self):
        """Сохраняет настройки"""
        # Настройки изображений
        self.settings.set('image_quality', self.quality_slider.value())
        self.settings.set('image_max_width', self.max_width_spin.value() if self.max_width_spin.value() > 0 else None)
        self.settings.set('image_max_height', self.max_height_spin.value() if self.max_height_spin.value() > 0 else None)

        # Настройки PDF
        self.settings.set('pdf_dpi', self.pdf_dpi_spin.value())
        self.settings.set('pdf_quality', self.pdf_quality_slider.value())
        self.settings.set('pdf_compress_level', self.pdf_compress_spin.value())
        self.settings.set('pdf_remove_metadata', self.pdf_remove_metadata_check.isChecked())
        self.settings.set('pdf_optimize_images', self.pdf_optimize_images_check.isChecked())
        self.settings.set('pdf_table_strategy', self.table_strategy_combo.currentText())

        # Настройки HEIC
        self.settings.set('heic_quality', self.heic_quality_slider.value())

        # Общие настройки
        self.settings.set('max_concurrent_jobs', self.max_jobs_spin.value())
        self.settings.set('auto_open_folder', self.auto_open_check.isChecked())
        self.settings.set('keep_original_name', self.keep_name_check.isChecked())
        self.settings.set('show_notifications', self.notifications_check.isChecked())

        self.show_info_signal.emit("Успех", "Настройки сохранены!")

    def _update_max_concurrent(self, value: int):
        """Обновляет максимальное количество одновременных задач"""
        self.job_manager.max_concurrent = value

    def on_input_format_changed(self, format_name: str):
        """Обработчик изменения входного формата"""
        if format_name == 'Все' or not format_name:
            self.output_format_combo.clear()
            self.output_format_combo.setEnabled(False)
            self.output_format_combo.addItem("Сначала выберите формат")
            self.convert_btn.setEnabled(False)
            return

        self.output_format_combo.setEnabled(True)
        self.output_format_combo.clear()

        formats = ConverterFactory.get_output_formats_for_input(format_name)
        if formats:
            self.output_format_combo.addItems(formats)
            if len(formats) > 0:
                self.output_format_combo.setCurrentIndex(0)
        else:
            self.output_format_combo.addItem("Нет доступных форматов")
            self.output_format_combo.setEnabled(False)

        self.check_file_formats()
        self.update_convert_button()

    def detect_file_format(self, file_path: Path) -> str:
        """Определяет формат файла по расширению"""
        ext = file_path.suffix.lower().lstrip('.')

        supported_formats = {
            'docx': 'docx', 'doc': 'doc', 'pdf': 'pdf',
            'pptx': 'pptx', 'ppt': 'ppt', 'pps': 'pps', 'ppsx': 'ppsx',
            'png': 'png', 'jpg': 'jpg', 'jpeg': 'jpg',
            'webp': 'webp', 'bmp': 'bmp', 'gif': 'gif', 'tiff': 'tiff',
            'heic': 'heic', 'heif': 'heif',
            'xlsx': 'xlsx', 'xls': 'xls', 'csv': 'csv',
            'odt': 'odt', 'rtf': 'rtf', 'txt': 'txt'
        }

        return supported_formats.get(ext, ext)

    def check_file_formats(self):
        """Проверяет соответствие форматов файлов выбранному формату"""
        input_format = self.input_format_combo.currentText()
        if input_format == 'Все' or not input_format:
            return True

        all_valid = True
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = Path(item.data(Qt.ItemDataRole.UserRole))
            ext = file_path.suffix.lower().lstrip('.')

            if ext != input_format:
                item.setForeground(Qt.GlobalColor.red)
                all_valid = False
            else:
                item.setForeground(Qt.GlobalColor.white)

        return all_valid

    def update_convert_button(self):
        """Обновляет состояние кнопки конвертации"""
        # Если конвертация уже идет, не даем нажать
        if self.conversion_in_progress:
            self.convert_btn.setEnabled(False)
            return

        has_files = self.file_list.count() > 0
        has_format = self.input_format_combo.currentText() != 'Все' and self.input_format_combo.currentText()
        has_output = bool(self.output_format_combo.currentText())

        valid_files = True
        if has_files and has_format:
            input_format = self.input_format_combo.currentText()
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                ext = file_path.suffix.lower().lstrip('.')
                if ext != input_format:
                    valid_files = False
                    break

        enabled = has_files and has_format and has_output and valid_files
        self.convert_btn.setEnabled(enabled)

    def add_files(self):
        """Добавляет файлы через диалог"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            str(Path.home()),
            "Все файлы (*.*)"
        )

        for file_path in files:
            self.add_file_to_list(Path(file_path))

    def add_folder(self):
        """Добавляет папку с файлами"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с файлами",
            str(Path.home())
        )

        if folder:
            folder_path = Path(folder)
            for ext in ConverterFactory.get_input_formats():
                for file_path in folder_path.glob(f"*.{ext}"):
                    self.add_file_to_list(file_path)

    def add_file_to_list(self, file_path: Path):
        """Добавляет файл в список"""
        ext = file_path.suffix.lower().lstrip('.')
        if ext not in ConverterFactory.get_input_formats():
            size_str = get_file_size_str(file_path)
            item_text = f"⚠️ {file_path.name} ({size_str}) - формат {ext} не поддерживается"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            item.setForeground(Qt.GlobalColor.red)
            self.file_list.addItem(item)
            return

        size_str = get_file_size_str(file_path)
        item_text = f"📄 {file_path.name} ({size_str})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.file_list.addItem(item)

        self.settings.add_recent_file(str(file_path))

        current_format = self.input_format_combo.currentText()
        if current_format == 'Все' or not current_format:
            detected_format = self.detect_file_format(file_path)
            if detected_format in ConverterFactory.get_input_formats():
                index = self.input_format_combo.findText(detected_format)
                if index >= 0:
                    self.input_format_combo.setCurrentIndex(index)

        self.check_file_formats()
        self.update_convert_button()
        self.update_file_count()

    def clear_files(self):
        """Очищает список файлов"""
        self.file_list.clear()
        self.update_convert_button()
        self.update_file_count()
        self.status_label.setText("Готов к работе")

    def update_file_count(self):
        """Обновляет счетчик файлов"""
        count = self.file_list.count()
        if count == 0:
            self.status_label.setText("Готов к работе")
        else:
            valid_count = 0
            input_format = self.input_format_combo.currentText()
            for i in range(count):
                item = self.file_list.item(i)
                file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                ext = file_path.suffix.lower().lstrip('.')
                if ext == input_format or input_format == 'Все':
                    valid_count += 1
            self.status_label.setText(f"Готов к работе ({valid_count}/{count} файл(ов) соответствуют формату)")

    def show_file_context_menu(self, position):
        """Показывает контекстное меню для файлов"""
        menu = QMenu()

        remove_action = QAction("🗑️ Удалить из списка", menu)
        remove_all_action = QAction("🗑️ Удалить все", menu)
        clear_invalid_action = QAction("⚠️ Удалить неверные форматы", menu)

        menu.addAction(remove_action)
        menu.addAction(remove_all_action)
        menu.addSeparator()
        menu.addAction(clear_invalid_action)

        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == remove_action:
            for item in self.file_list.selectedItems():
                self.file_list.takeItem(self.file_list.row(item))
            self.update_convert_button()
            self.update_file_count()

        elif action == remove_all_action:
            self.file_list.clear()
            self.update_convert_button()
            self.update_file_count()

        elif action == clear_invalid_action:
            input_format = self.input_format_combo.currentText()
            if input_format != 'Все':
                for i in range(self.file_list.count() - 1, -1, -1):
                    item = self.file_list.item(i)
                    file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                    ext = file_path.suffix.lower().lstrip('.')
                    if ext != input_format:
                        self.file_list.takeItem(i)
                self.update_convert_button()
                self.update_file_count()

    def start_conversion(self):
        """Запускает конвертацию"""
        if self.file_list.count() == 0:
            self.show_warning_signal.emit("Ошибка", "Нет файлов для конвертации")
            return

        input_format = self.input_format_combo.currentText()
        output_format = self.output_format_combo.currentText()

        if input_format == 'Все':
            self.show_warning_signal.emit(
                "Ошибка",
                "Пожалуйста, выберите конкретный входной формат"
            )
            return

        if not output_format:
            self.show_warning_signal.emit("Ошибка", "Выберите выходной формат")
            return

        converter = ConverterFactory.get_converter(input_format, output_format)
        if not converter:
            self.show_warning_signal.emit(
                "Ошибка",
                f"Конвертация из {input_format} в {output_format} не поддерживается"
            )
            return

        self.settings.add_recent_format(input_format, output_format)

        output_dir = self.settings.get('output_directory')
        if not output_dir:
            output_dir = str(Path.home() / 'Downloads')

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения",
            output_dir
        )

        if not output_dir:
            return

        self.settings.set('output_directory', output_dir)

        added_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            input_path = Path(item.data(Qt.ItemDataRole.UserRole))

            ext = input_path.suffix.lower().lstrip('.')
            if ext != input_format:
                continue

            if self.settings.get('keep_original_name', True):
                output_name = f"{input_path.stem}.{output_format}"
            else:
                output_name = f"converted_{added_count+1}.{output_format}"

            output_path = Path(output_dir) / output_name
            output_path = get_unique_filename(output_path)

            ensure_output_directory(output_path)

            # Передаем настройки в конвертер
            kwargs = {}

            # Настройки для изображений
            if output_format in ['jpg', 'jpeg', 'webp']:
                kwargs['quality'] = self.settings.get('image_quality', 85)

            # Настройки для PDF
            if input_format == 'pdf':
                if output_format in ['png', 'jpg', 'jpeg', 'webp']:
                    kwargs['dpi'] = self.settings.get('pdf_dpi', 200)
                    kwargs['quality'] = self.settings.get('pdf_quality', 85)
                elif output_format in ['xlsx', 'xls', 'csv']:
                    kwargs['table_strategy'] = self.settings.get('pdf_table_strategy', 'auto')
                elif output_format == 'pdf':
                    kwargs['compression_level'] = self.settings.get('pdf_compress_level', 6)
                    kwargs['remove_metadata'] = self.settings.get('pdf_remove_metadata', False)
                    kwargs['optimize_images'] = self.settings.get('pdf_optimize_images', True)
                elif output_format in ['pptx', 'ppt']:
                    kwargs['dpi'] = self.settings.get('pdf_dpi', 150)
                    kwargs['quality'] = self.settings.get('pdf_quality', 85)

            # Настройки для HEIC
            if input_format in ['heic', 'heif']:
                kwargs['quality'] = self.settings.get('heic_quality', 85)

            self.job_manager.add_job(
                input_path,
                output_path,
                input_format,
                output_format,
                **kwargs
            )
            added_count += 1

        if added_count == 0:
            self.show_warning_signal.emit(
                "Ошибка",
                f"Нет файлов формата {input_format} для конвертации"
            )
            return

        # Блокируем кнопку и запускаем таймер
        self.conversion_in_progress = True
        self.convert_btn.setEnabled(False)
        self.status_label.setText(f"Конвертация запущена ({added_count} файлов)")

        # Запускаем таймер если еще не запущен
        if not self.status_timer.isActive():
            self.status_timer.start()

    def update_status(self):
        """Обновляет статус"""
        active = self.job_manager.get_active_jobs_count()
        jobs = self.job_manager.get_all_jobs()

        if not jobs:
            return

        total = len(jobs)
        completed = sum(1 for job in jobs if job.get_status() == JobStatus.COMPLETED)
        failed = sum(1 for job in jobs if job.get_status() == JobStatus.FAILED)

        # Считаем средний прогресс
        if total > 0:
            total_progress = sum(job.get_progress() for job in jobs) // total
            self.total_progress.setValue(total_progress)

        self.status_label.setText(f"Активных: {active}, Завершено: {completed}/{total}")
        self.active_jobs_label.setText(f"Активных: {active}")

        # Проверяем завершение всех задач
        active_jobs = [j for j in jobs if j.get_status() in [JobStatus.PENDING, JobStatus.PROCESSING]]

        if not active_jobs and total > 0:
            self.status_timer.stop()
            self.conversion_in_progress = False
            self.update_convert_button()
            self.status_label.setText(f"Конвертация завершена! ({completed} успешно, {failed} с ошибками)")
            self.total_progress.setValue(100)
            self.active_jobs_label.setText("Активных: 0")

            # Очищаем список файлов от прогресса
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                text = item.text()
                if ' (' in text and '%)' in text:
                    text = text.split(' (')[0]
                    item.setText(text)

            if self.settings.get('auto_open_folder', True) and completed > 0:
                import subprocess
                output_dir = self.settings.get('output_directory')
                if output_dir:
                    try:
                        if sys.platform == 'win32':
                            subprocess.Popen(f'explorer "{output_dir}"', shell=True)
                        elif sys.platform == 'darwin':
                            subprocess.Popen(['open', output_dir])
                        else:
                            subprocess.Popen(['xdg-open', output_dir])
                    except Exception as e:
                        logger.error(f"Не удалось открыть папку: {e}")

    def on_job_started(self, job: ConversionJob):
        """Обработчик начала задачи"""
        self.log_text.append(f"✅ Начата конвертация: {job.input_path.name}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def on_job_progress(self, job: ConversionJob):
        """Обработчик прогресса задачи"""
        # Используем сигнал для безопасного обновления UI
        self.update_file_item_signal.emit(str(job.input_path), job.get_progress())
        self.update_status_signal.emit()

    def on_job_completed(self, job: ConversionJob):
        """Обработчик завершения задачи"""
        self.log_text.append(f"✔️ Завершено: {job.input_path.name} -> {job.output_path.name}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

        if self.settings.get('show_notifications', True):
            self.show_info_signal.emit(
                "Конвертация завершена",
                f"Файл {job.input_path.name} успешно сконвертирован!"
            )

        self.update_status_signal.emit()

    def on_job_failed(self, job: ConversionJob):
        """Обработчик ошибки задачи"""
        self.log_text.append(f"❌ Ошибка: {job.input_path.name} - {job.error_message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

        if self.settings.get('show_notifications', True):
            self.show_error_signal.emit(
                "Ошибка конвертации",
                f"Не удалось сконвертировать {job.input_path.name}\n\n{job.error_message}"
            )

        self.update_status_signal.emit()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработчик перетаскивания файлов"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Обработчик сброса файлов"""
        for url in event.mimeData().urls():
            file_path = Path(url.toLocalFile())
            if file_path.is_file():
                self.add_file_to_list(file_path)
            elif file_path.is_dir():
                for ext in ConverterFactory.get_input_formats():
                    for f in file_path.glob(f"*.{ext}"):
                        self.add_file_to_list(f)

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.status_timer.stop()
        self.job_manager.stop()
        self.worker.quit()
        self.worker.wait()
        event.accept()