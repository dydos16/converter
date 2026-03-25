"""
Управление очередью задач конвертации
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from threading import Thread, Lock, Event
from queue import Queue
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

    def update_progress(self, progress: int):
        """Обновляет прогресс задачи"""
        self.progress = progress

    def mark_completed(self):
        """Отмечает задачу как выполненную"""
        self.status = JobStatus.COMPLETED
        self.progress = 100
        self.completed_at = datetime.now()

    def mark_failed(self, error: str):
        """Отмечает задачу как проваленную"""
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.now()

    def mark_cancelled(self):
        """Отмечает задачу как отмененную"""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now()


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

    def start(self):
        """Запускает обработку очереди"""
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("JobManager запущен")

    def stop(self):
        """Останавливает обработку очереди"""
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("JobManager остановлен")

    def add_job(self, input_path: Path, output_path: Path,
                input_format: str, output_format: str) -> str:
        """
        Добавляет новую задачу в очередь

        Returns:
            str: ID задачи
        """
        job_id = str(uuid.uuid4())

        job = ConversionJob(
            id=job_id,
            input_path=input_path,
            output_path=output_path,
            input_format=input_format,
            output_format=output_format
        )

        with self.lock:
            self.jobs[job_id] = job
            self.queue.put(job)

        logger.info(f"Добавлена задача {job_id}: {input_path} -> {output_path}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        """Отменяет задачу"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                job.mark_cancelled()
                logger.info(f"Задача {job_id} отменена")
                return True
            elif job and job.status == JobStatus.PROCESSING:
                logger.warning(f"Нельзя отменить выполняющуюся задачу {job_id}")
                return False
        return False

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Возвращает статус задачи"""
        job = self.jobs.get(job_id)
        return job.status if job else None

    def get_all_jobs(self) -> List[ConversionJob]:
        """Возвращает все задачи"""
        with self.lock:
            return list(self.jobs.values())

    def get_active_jobs_count(self) -> int:
        """Возвращает количество активных задач"""
        return len(self.active_jobs)

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
                except:
                    # Нет задач в очереди
                    continue

                # Проверяем, не отменена ли задача
                if job.status == JobStatus.CANCELLED:
                    continue

                # Запускаем задачу в отдельном потоке
                thread = Thread(target=self._process_job, args=(job,))
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
            job.status = JobStatus.PROCESSING
            self._trigger_callback('on_job_started', job)

            # Создаем конвертер
            converter = ConverterFactory.get_converter(
                job.input_format,
                job.output_format
            )

            if not converter:
                raise Exception(f"Конвертер не найден для {job.input_format} -> {job.output_format}")

            # Устанавливаем коллбеки
            converter.progress_callback = lambda p: self._update_job_progress(job.id, p)
            converter.status_callback = lambda s: logger.info(f"Job {job.id}: {s}")
            converter.error_callback = lambda e: logger.error(f"Job {job.id}: {e}")

            job.converter = converter

            # Выполняем конвертацию
            success = converter.convert(job.input_path, job.output_path)

            if success:
                job.mark_completed()
                self._trigger_callback('on_job_completed', job)
                logger.success(f"Задача {job.id} успешно выполнена")
            else:
                job.mark_failed("Конвертация не удалась")
                self._trigger_callback('on_job_failed', job)
                logger.error(f"Задача {job.id} провалилась")

        except Exception as e:
            job.mark_failed(str(e))
            self._trigger_callback('on_job_failed', job)
            logger.exception(f"Ошибка при выполнении задачи {job.id}: {e}")

        finally:
            with self.lock:
                if job.id in self.active_jobs:
                    del self.active_jobs[job.id]

    def _update_job_progress(self, job_id: str, progress: int):
        """Обновляет прогресс задачи"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.update_progress(progress)
                self._trigger_callback('on_job_progress', job)

    def register_callback(self, event: str, callback: Callable):
        """Регистрирует callback для события"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callback(self, event: str, job: ConversionJob):
        """Вызывает все callback'и для события"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Ошибка в callback {event}: {e}")