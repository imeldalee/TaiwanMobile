import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, Iterable, Iterator, List

from log_config import get_logger, log_with_context
from models import Task

logger = get_logger("task_store")


class TaskStore(ABC):
    @abstractmethod
    def add(self, task):
        pass

    @abstractmethod
    def add_many(self, tasks):
        pass

    @abstractmethod
    def due_count(self, time_slot):
        pass

    @abstractmethod
    def iter_due_batches(self, time_slot, batch_size):
        pass


class InMemoryTaskStore(TaskStore):
    """Tasks indexed by time slot — O(1) lookup, O(k) iteration for k due tasks."""

    def __init__(self):
        self._by_time = defaultdict(list)  # type: Dict[str, List[Task]]
        self._total = 0

    @property
    def total_tasks(self):
        return self._total

    def add(self, task):
        self._by_time[task.time].append(task)
        self._total += 1
        logger.debug(
            "Task indexed task_id=%s time=%s (total=%d)",
            task.task_id,
            task.time,
            self._total,
        )

    def add_many(self, tasks):
        count = 0
        for task in tasks:
            self.add(task)
            count += 1
        log_with_context(
            logger,
            logging.DEBUG,
            "Batch indexed",
            count=count,
            store_total=self._total,
        )

    def due_count(self, time_slot):
        return len(self._by_time.get(time_slot, []))

    def iter_due_batches(self, time_slot, batch_size):
        tasks = self._by_time.get(time_slot, [])
        if batch_size < 1:
            logger.warning(
                "Invalid batch_size=%d for slot=%s; coercing to %d",
                batch_size,
                time_slot,
                len(tasks) or 1,
            )
            batch_size = len(tasks) or 1
        for offset in range(0, len(tasks), batch_size):
            yield tasks[offset : offset + batch_size]
