"""
Управление очередью задач конвертации
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from threading import Thread, Lock, Event
from queue import Queue, Empty
import uuid
from loguru import logger

from src.converters.factory import ConverterFactory


class JobStatus(Enum):
    """Статусы задач"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ConversionJob:
    """Задача конвертации"""
    id: str
    input_path: Path
    output_path: Path
    input_format: str
    output_format: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    converter: Optional[object] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)

    # Блокировка для потокобезопасного обновления полей
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def update_progress(self, progress: int):
        """Обновляет прогресс задачи (потокобезопасно)"""
        with self._lock:
            self.progress = min(max(progress, 0), 100)

    def mark_completed(self):
        """Отмечает задачу как выполненную (потокобезопасно)"""
        with self._lock:
            self.status = JobStatus.COMPLETED
            self.progress = 100
            self.completed_at = datetime.now()

    def mark_failed(self, error: str):
        """Отмечает задачу как проваленную (потокобезопасно)"""
        with self._lock:
            self.status = JobStatus.FAILED
            self.error_message = error
            self.completed_at = datetime.now()

    def mark_cancelled(self):
        """Отмечает задачу как отмененную (потокобезопасно)"""
        with self._lock:
            self.status = JobStatus.CANCELLED
            self.completed_at = datetime.now()

    def mark_processing(self):
        """Отмечает задачу как выполняющуюся (потокобезопасно)"""
        with self._lock:
            self.status = JobStatus.PROCESSING

    def get_status(self) -> JobStatus:
        """Возвращает статус (потокобезопасно)"""
        with self._lock:
            return self.status

    def get_progress(self) -> int:
        """Возвращает прогресс (потокобезопасно)"""
        with self._lock:
            return self.progress

    def to_dict(self) -> dict:
        """Преобразует задачу в словарь"""
        with self._lock:
            return {
                'id': self.id,
                'input_path': str(self.input_path),
                'output_path': str(self.output_path),
                'input_format': self.input_format,
                'output_format': self.output_format,
                'status': self.status.value,
                'progress': self.progress,
                'error_message': self.error_message,
                'created_at': self.created_at.isoformat(),
                'completed_at': self.completed_at.isoformat() if self.completed_at else None
            }


class JobManager:
    """Менеджер очереди задач"""

    def __init__(self, max_concurrent: int = 3):
        self.queue = Queue()
        self.jobs: dict[str, ConversionJob] = {}
        self.active_jobs: dict[str, Thread] = {}
        self.max_concurrent = max_concurrent
        self.lock = Lock()
        self.stop_event = Event()
        self.worker_thread = None
        self.callbacks = {
            'on_job_started': [],
            'on_job_progress': [],
            'on_job_completed': [],
            'on_job_failed': []
        }
        self._job_counters = {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0, 'cancelled': 0}
        self._callbacks_lock = Lock()

    def start(self):
        """Запускает обработку очереди"""
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = Thread(target=self._process_queue, daemon=True, name="JobManagerWorker")
            self.worker_thread.start()
            logger.info("JobManager запущен")

    def stop(self):
        """Останавливает обработку очереди"""
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        logger.info("JobManager остановлен")

    def add_job(self, input_path: Path, output_path: Path,
                input_format: str, output_format: str, **kwargs) -> str:
        """
        Добавляет новую задачу в очередь

        Args:
            input_path: Путь к входному файлу
            output_path: Путь к выходному файлу
            input_format: Входной формат
            output_format: Выходной формат
            **kwargs: Дополнительные параметры для конвертера

        Returns:
            str: ID задачи
        """
        job_id = str(uuid.uuid4())

        job = ConversionJob(
            id=job_id,
            input_path=input_path,
            output_path=output_path,
            input_format=input_format,
            output_format=output_format,
            kwargs=kwargs
        )

        with self.lock:
            self.jobs[job_id] = job
            self.queue.put(job)
            self._job_counters['pending'] += 1

        logger.info(f"Добавлена задача {job_id}: {input_path.name} -> {output_path.name}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        """Отменяет задачу"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            current_status = job.get_status()

            if current_status == JobStatus.PENDING:
                job.mark_cancelled()
                self._job_counters['pending'] -= 1
                self._job_counters['cancelled'] += 1
                logger.info(f"Задача {job_id} отменена")
                return True
            elif current_status == JobStatus.PROCESSING:
                logger.warning(f"Нельзя отменить выполняющуюся задачу {job_id}")
                return False

        return False

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Возвращает статус задачи"""
        job = self.jobs.get(job_id)
        return job.get_status() if job else None

    def get_job(self, job_id: str) -> Optional[ConversionJob]:
        """Возвращает задачу по ID"""
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> List[ConversionJob]:
        """Возвращает все задачи"""
        with self.lock:
            return list(self.jobs.values())

    def get_statistics(self) -> dict:
        """Возвращает статистику по задачам"""
        with self.lock:
            return {
                'pending': self._job_counters['pending'],
                'processing': self._job_counters['processing'],
                'completed': self._job_counters['completed'],
                'failed': self._job_counters['failed'],
                'cancelled': self._job_counters['cancelled'],
                'total': len(self.jobs),
                'active': len(self.active_jobs),
                'max_concurrent': self.max_concurrent
            }

    def get_active_jobs_count(self) -> int:
        """Возвращает количество активных задач"""
        with self.lock:
            return len(self.active_jobs)

    def get_queue_size(self) -> int:
        """Возвращает размер очереди"""
        return self.queue.qsize()

    def is_running(self) -> bool:
        """Проверяет, запущен ли менеджер"""
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def _process_queue(self):
        """Основной цикл обработки очереди"""
        while not self.stop_event.is_set():
            try:
                # Проверяем, можем ли запустить новую задачу
                if self.get_active_jobs_count() >= self.max_concurrent:
                    import time
                    time.sleep(0.5)
                    continue

                # Получаем следующую задачу с таймаутом
                try:
                    job = self.queue.get(timeout=1)
                except Empty:
                    continue

                # Проверяем статус задачи перед запуском
                if job.get_status() == JobStatus.CANCELLED:
                    continue

                # Отмечаем как выполняющуюся ПОД ЛОКОМ
                with self.lock:
                    # Повторная проверка статуса под локом
                    if job.get_status() == JobStatus.CANCELLED:
                        continue

                    job.mark_processing()
                    self._job_counters['pending'] -= 1
                    self._job_counters['processing'] += 1

                # Запускаем задачу в отдельном потоке
                thread = Thread(target=self._process_job, args=(job,), daemon=True)
                thread.daemon = True

                with self.lock:
                    self.active_jobs[job.id] = thread

                thread.start()

            except Exception as e:
                if not self.stop_event.is_set():
                    logger.error(f"Ошибка в процессе обработки очереди: {e}")
                    import time
                    time.sleep(1)

    def _process_job(self, job: ConversionJob):
        """Обрабатывает отдельную задачу"""
        try:
            # Уведомляем о начале
            self._trigger_callback('on_job_started', job)

            # Создаем конвертер
            converter = ConverterFactory.get_converter(
                job.input_format,
                job.output_format,
                **job.kwargs
            )

            if not converter:
                raise Exception(f"Конвертер не найден для {job.input_format} -> {job.output_format}")

            # Устанавливаем коллбеки с обновлением прогресса
            def progress_callback(p):
                job.update_progress(p)
                self._trigger_callback('on_job_progress', job)

            def status_callback(s):
                logger.debug(f"Job {job.id}: {s}")

            def error_callback(e):
                job.mark_failed(e)
                logger.error(f"Job {job.id}: {e}")

            converter.progress_callback = progress_callback
            converter.status_callback = status_callback
            converter.error_callback = error_callback

            job.converter = converter

            # PDF под паролем или битый — понятная причина вместо «document closed or encrypted»
            from src.converters.pdf_text import pdf_problem
            problem = pdf_problem(job.input_path)
            if problem:
                error_callback(problem)
                success = False
            else:
                success = converter.convert(job.input_path, job.output_path)

            if success:
                job.mark_completed()
                with self.lock:
                    self._job_counters['processing'] -= 1
                    self._job_counters['completed'] += 1
                self._trigger_callback('on_job_completed', job)
                logger.success(f"Задача {job.id} успешно выполнена")
            else:
                # Не затираем конкретную причину, если конвертер её уже сообщил
                job.mark_failed(job.error_message or "Конвертация не удалась")
                with self.lock:
                    self._job_counters['processing'] -= 1
                    self._job_counters['failed'] += 1
                self._trigger_callback('on_job_failed', job)
                logger.error(f"Задача {job.id} провалилась")

        except Exception as e:
            job.mark_failed(str(e))
            with self.lock:
                self._job_counters['processing'] -= 1
                self._job_counters['failed'] += 1
            self._trigger_callback('on_job_failed', job)
            logger.exception(f"Ошибка при выполнении задачи {job.id}: {e}")

        finally:
            with self.lock:
                if job.id in self.active_jobs:
                    del self.active_jobs[job.id]

    def register_callback(self, event: str, callback: Callable):
        """Регистрирует callback для события"""
        with self._callbacks_lock:
            if event in self.callbacks:
                self.callbacks[event].append(callback)
                logger.debug(f"Зарегистрирован callback для события {event}")

    def unregister_callback(self, event: str, callback: Callable):
        """Удаляет callback для события"""
        with self._callbacks_lock:
            if event in self.callbacks and callback in self.callbacks[event]:
                self.callbacks[event].remove(callback)
                logger.debug(f"Удален callback для события {event}")

    def _trigger_callback(self, event: str, job: ConversionJob):
        """Вызывает все callback'и для события (потокобезопасно)"""
        callbacks_copy = []
        with self._callbacks_lock:
            callbacks_copy = self.callbacks.get(event, []).copy()

        for callback in callbacks_copy:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Ошибка в callback {event}: {e}")