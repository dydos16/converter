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
    QTabWidget, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont

from src.converters.factory import ConverterFactory
from src.core.job_manager import JobManager, ConversionJob, JobStatus
from src.core.settings import Settings
from src.utils.helpers import get_file_size_str, get_unique_filename, ensure_output_directory


class ConversionWorker(QThread):
    """Поток для выполнения конвертации"""
    progress_updated = Signal(str, int)
    job_completed = Signal(str, bool, str)

    def __init__(self, job_manager: JobManager):
        super().__init__()
        self.job_manager = job_manager

    def run(self):
        self.job_manager.start()
        self.exec()


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.job_manager = JobManager(max_concurrent=self.settings.get('max_concurrent_jobs', 3))
        self.worker = ConversionWorker(self.job_manager)

        self.setup_ui()
        self.setup_callbacks()
        self.load_settings()

        self.worker.start()

    def setup_ui(self):
        """Настраивает интерфейс"""
        self.setWindowTitle("File Converter Pro")
        self.setGeometry(100, 100, 1200, 800)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QVBoxLayout(central_widget)

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

    def setup_conversion_tab(self, parent: QWidget):
        """Настраивает вкладку конвертации"""
        layout = QVBoxLayout(parent)

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

        buttons_layout.addWidget(self.add_files_btn)
        buttons_layout.addWidget(self.add_folder_btn)
        buttons_layout.addWidget(self.clear_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.convert_btn)

        top_panel.addWidget(buttons_group)

        layout.addLayout(top_panel)

        # Список файлов
        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(300)
        layout.addWidget(QLabel("Файлы для конвертации:"))
        layout.addWidget(self.file_list)

        # Панель прогресса
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Общий прогресс:"))
        self.total_progress = QProgressBar()
        progress_layout.addWidget(self.total_progress)
        layout.addLayout(progress_layout)

        # Включаем Drag & Drop
        self.setAcceptDrops(True)

    def setup_settings_tab(self, parent: QWidget):
        """Настраивает вкладку настроек"""
        layout = QVBoxLayout(parent)

        # Настройки изображений
        image_group = QGroupBox("Настройки изображений")
        image_layout = QVBoxLayout(image_group)

        # Качество
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Качество JPEG:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(self.settings.get('image_quality', 85))
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
        self.max_width_spin.setValue(self.settings.get('image_max_width', 0))

        size_layout.addWidget(self.max_width_spin)
        size_layout.addWidget(QLabel("Макс. высота:"))
        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(0, 10000)
        self.max_height_spin.setSpecialValueText("Без ограничений")
        self.max_height_spin.setValue(self.settings.get('image_max_height', 0))

        image_layout.addLayout(size_layout)
        layout.addWidget(image_group)

        # Общие настройки
        general_group = QGroupBox("Общие настройки")
        general_layout = QVBoxLayout(general_group)

        self.auto_open_check = QCheckBox("Открывать папку после конвертации")
        self.auto_open_check.setChecked(self.settings.get('auto_open_folder', True))

        self.keep_name_check = QCheckBox("Сохранять оригинальное имя файла")
        self.keep_name_check.setChecked(self.settings.get('keep_original_name', True))

        self.notifications_check = QCheckBox("Показывать уведомления")
        self.notifications_check.setChecked(self.settings.get('show_notifications', True))

        general_layout.addWidget(self.auto_open_check)
        general_layout.addWidget(self.keep_name_check)
        general_layout.addWidget(self.notifications_check)

        layout.addWidget(general_group)

        # Кнопка сохранения
        save_btn = QPushButton("Сохранить настройки")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

    def setup_log_tab(self, parent: QWidget):
        """Настраивает вкладку лога"""
        layout = QVBoxLayout(parent)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monospace", 9))
        layout.addWidget(self.log_text)

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
        self.settings.set('image_quality', self.quality_slider.value())
        self.settings.set('image_max_width', self.max_width_spin.value() or None)
        self.settings.set('image_max_height', self.max_height_spin.value() or None)
        self.settings.set('auto_open_folder', self.auto_open_check.isChecked())
        self.settings.set('keep_original_name', self.keep_name_check.isChecked())
        self.settings.set('show_notifications', self.notifications_check.isChecked())

        QMessageBox.information(self, "Успех", "Настройки сохранены!")

    def on_input_format_changed(self, format_name: str):
        """Обработчик изменения входного формата"""
        if format_name == 'Все':
            self.output_format_combo.clear()
            self.output_format_combo.setEnabled(False)
            return

        self.output_format_combo.setEnabled(True)
        self.output_format_combo.clear()

        formats = ConverterFactory.get_output_formats_for_input(format_name)
        self.output_format_combo.addItems(formats)

        # Восстанавливаем последний использованный формат
        recent_formats = self.settings.get('recent_formats', [])
        for fmt in recent_formats:
            if fmt.startswith(f"{format_name}→"):
                out = fmt.split('→')[1]
                if out in formats:
                    index = self.output_format_combo.findText(out)
                    if index >= 0:
                        self.output_format_combo.setCurrentIndex(index)
                        break

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
            # Ищем поддерживаемые файлы
            for ext in ConverterFactory.get_input_formats():
                for file_path in folder_path.glob(f"*.{ext}"):
                    self.add_file_to_list(file_path)

    def add_file_to_list(self, file_path: Path):
        """Добавляет файл в список"""
        # Проверяем формат
        ext = file_path.suffix.lower().lstrip('.')
        if ext not in ConverterFactory.get_input_formats():
            QMessageBox.warning(
                self,
                "Не поддерживается",
                f"Формат {ext} не поддерживается для конвертации"
            )
            return

        # Добавляем в список
        size_str = get_file_size_str(file_path)
        item_text = f"📄 {file_path.name} ({size_str})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.file_list.addItem(item)

        # Сохраняем в историю
        self.settings.add_recent_file(str(file_path))

        self.update_convert_button()

    def clear_files(self):
        """Очищает список файлов"""
        self.file_list.clear()
        self.update_convert_button()

    def start_conversion(self):
        """Запускает конвертацию"""
        if self.file_list.count() == 0:
            return

        input_format = self.input_format_combo.currentText()
        output_format = self.output_format_combo.currentText()

        if input_format == 'Все':
            QMessageBox.warning(
                self,
                "Ошибка",
                "Пожалуйста, выберите конкретный входной формат"
            )
            return

        # Сохраняем выбранные форматы
        self.settings.add_recent_format(input_format, output_format)

        # Получаем директорию для сохранения
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

        # Создаем задачи
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            input_path = Path(item.data(Qt.ItemDataRole.UserRole))

            # Формируем имя выходного файла
            if self.settings.get('keep_original_name', True):
                output_name = f"{input_path.stem}.{output_format}"
            else:
                output_name = f"converted_{i+1}.{output_format}"

            output_path = Path(output_dir) / output_name
            output_path = get_unique_filename(output_path)

            # Создаем директорию если нужно
            ensure_output_directory(output_path)

            # Добавляем задачу
            self.job_manager.add_job(
                input_path,
                output_path,
                input_format,
                output_format
            )

        # Блокируем кнопку
        self.convert_btn.setEnabled(False)
        self.status_label.setText(f"Конвертация запущена ({self.job_manager.get_active_jobs_count()} активных задач)")

        # Запускаем таймер для обновления статуса
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

    def update_status(self):
        """Обновляет статус"""
        active = self.job_manager.get_active_jobs_count()
        total = len(self.job_manager.get_all_jobs())
        completed = sum(1 for job in self.job_manager.get_all_jobs()
                        if job.status == JobStatus.COMPLETED)

        self.status_label.setText(f"Активных: {active}, Завершено: {completed}/{total}")

        # Обновляем общий прогресс
        if total > 0:
            progress = int((completed / total) * 100)
            self.total_progress.setValue(progress)

        # Если все задачи завершены
        if completed == total and total > 0:
            self.status_timer.stop()
            self.convert_btn.setEnabled(True)
            self.status_label.setText("Конвертация завершена!")

            if self.settings.get('auto_open_folder', True):
                import subprocess
                output_dir = self.settings.get('output_directory')
                if sys.platform == 'win32':
                    subprocess.Popen(f'explorer "{output_dir}"')
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', output_dir])
                else:
                    subprocess.Popen(['xdg-open', output_dir])

    def update_convert_button(self):
        """Обновляет состояние кнопки конвертации"""
        has_files = self.file_list.count() > 0
        has_format = self.input_format_combo.currentText() != 'Все'
        self.convert_btn.setEnabled(has_files and has_format)

    def on_job_started(self, job: ConversionJob):
        """Обработчик начала задачи"""
        self.log_text.append(f"✅ Начата конвертация: {job.input_path.name}")

    def on_job_progress(self, job: ConversionJob):
        """Обработчик прогресса задачи"""
        pass

    def on_job_completed(self, job: ConversionJob):
        """Обработчик завершения задачи"""
        self.log_text.append(f"✔️ Завершено: {job.input_path.name} -> {job.output_path.name}")

        if self.settings.get('show_notifications', True):
            QMessageBox.information(
                self,
                "Конвертация завершена",
                f"Файл {job.input_path.name} успешно сконвертирован!"
            )

    def on_job_failed(self, job: ConversionJob):
        """Обработчик ошибки задачи"""
        self.log_text.append(f"❌ Ошибка: {job.input_path.name} - {job.error_message}")

        if self.settings.get('show_notifications', True):
            QMessageBox.warning(
                self,
                "Ошибка конвертации",
                f"Не удалось сконвертировать {job.input_path.name}\n\n{job.error_message}"
            )

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
        self.job_manager.stop()
        self.worker.quit()
        self.worker.wait()
        event.accept()