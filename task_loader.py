"""Task ingestion — separated from storage indexing."""

import logging
from typing import Iterable, List

from exceptions import TaskLoadError, TaskValidationError
from log_config import get_logger, log_with_context
from models import Task
from task_store import TaskStore

logger = get_logger("task_loader")


def load_dicts_into_store(store, task_dicts, parse_batch_size=10000):
    """
    Parse task dicts in chunks and index them in the store.

    Raises TaskLoadError if parsing fails after partial loads.
    """
    batch = []  # type: List[Task]
    loaded = 0
    index = 0

    try:
        for data in task_dicts:
            index += 1
            batch.append(Task.from_dict(data))
            if len(batch) >= parse_batch_size:
                store.add_many(batch)
                loaded += len(batch)
                batch = []
        if batch:
            store.add_many(batch)
            loaded += len(batch)
    except TaskValidationError as exc:
        log_with_context(
            logger,
            logging.ERROR,
            "Task load failed",
            index=index,
            loaded_before_failure=loaded,
            error=str(exc),
        )
        raise TaskLoadError(
            "Failed loading task at index {}: {}".format(index, exc.message),
            loaded_count=loaded,
            cause=exc,
        )

    log_with_context(
        logger,
        logging.INFO,
        "Tasks loaded into store",
        count=loaded,
        store_total=store.total_tasks,
    )
    return loaded
