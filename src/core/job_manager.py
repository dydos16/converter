"""
Управление очередью задач конвертации
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
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
    kwargs: Dict[str, Any] = field(default_factory=dict)  # Дополнительные параметры

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

    def to_dict(self) -> dict:
        """Преобразует задачу в словарь"""
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
        if self.worker_thread:
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
            if job and job.status == JobStatus.PENDING:
                job.mark_cancelled()
                self._job_counters['pending'] -= 1
                self._job_counters['cancelled'] += 1
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

    def get_job(self, job_id: str) -> Optional[ConversionJob]:
        """Возвращает задачу по ID"""
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> List[ConversionJob]:
        """Возвращает все задачи"""
        with self.lock:
            return list(self.jobs.values())

    def get_jobs_by_status(self, status: JobStatus) -> List[ConversionJob]:
        """Возвращает задачи с определенным статусом"""
        with self.lock:
            return [job for job in self.jobs.values() if job.status == status]

    def get_active_jobs_count(self) -> int:
        """Возвращает количество активных задач"""
        return len(self.active_jobs)

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

    def clear_completed_jobs(self):
        """Очищает завершенные задачи"""
        with self.lock:
            to_remove = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    to_remove.append(job_id)

            for job_id in to_remove:
                del self.jobs[job_id]

            logger.info(f"Очищено {len(to_remove)} завершенных задач")

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
                thread = Thread(target=self._process_job, args=(job,), daemon=True)
                thread.daemon = True

                with self.lock:
                    self.active_jobs[job.id] = thread
                    self._job_counters['pending'] -= 1
                    self._job_counters['processing'] += 1

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

            # Создаем конвертер с передачей дополнительных параметров
            converter = ConverterFactory.get_converter(
                job.input_format,
                job.output_format,
                **job.kwargs
            )

            if not converter:
                raise Exception(f"Конвертер не найден для {job.input_format} -> {job.output_format}")

            # Устанавливаем коллбеки
            converter.progress_callback = lambda p: self._update_job_progress(job.id, p)
            converter.status_callback = lambda s: logger.debug(f"Job {job.id}: {s}")
            converter.error_callback = lambda e: self._update_job_error(job.id, e)

            job.converter = converter

            # Выполняем конвертацию
            success = converter.convert(job.input_path, job.output_path)

            if success:
                job.mark_completed()
                with self.lock:
                    self._job_counters['processing'] -= 1
                    self._job_counters['completed'] += 1
                self._trigger_callback('on_job_completed', job)
                logger.success(f"Задача {job.id} успешно выполнена")
            else:
                job.mark_failed("Конвертация не удалась")
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

    def _update_job_progress(self, job_id: str, progress: int):
        """Обновляет прогресс задачи"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.update_progress(progress)
                self._trigger_callback('on_job_progress', job)

    def _update_job_error(self, job_id: str, error: str):
        """Обновляет ошибку задачи"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.error_message = error

    def register_callback(self, event: str, callback: Callable):
        """Регистрирует callback для события"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            logger.debug(f"Зарегистрирован callback для события {event}")

    def unregister_callback(self, event: str, callback: Callable):
        """Удаляет callback для события"""
        if event in self.callbacks and callback in self.callbacks[event]:
            self.callbacks[event].remove(callback)
            logger.debug(f"Удален callback для события {event}")

    def _trigger_callback(self, event: str, job: ConversionJob):
        """Вызывает все callback'и для события"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Ошибка в callback {event}: {e}")

    def get_queue_size(self) -> int:
        """Возвращает размер очереди"""
        return self.queue.qsize()

    def is_running(self) -> bool:
        """Проверяет, запущен ли менеджер"""
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def wait_for_completion(self, timeout: Optional[float] = None):
        """Ожидает завершения всех задач"""
        start_time = datetime.now()
        while True:
            if timeout is not None:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    logger.warning(f"Таймаут ожидания завершения задач ({timeout} сек)")
                    return False

            with self.lock:
                active_count = len([j for j in self.jobs.values()
                                   if j.status in [JobStatus.PENDING, JobStatus.PROCESSING]])

            if active_count == 0:
                return True

            import time
            time.sleep(0.5)