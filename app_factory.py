"""Application composition — wires dependencies without business logic."""

import logging

from config import BATCH_SIZE, MAX_WORKERS
from executor import DefaultTaskExecutor, TaskExecutorRegistry
from log_config import get_logger, log_with_context, setup_logging
from scheduler import Scheduler
from task_loader import load_dicts_into_store
from task_store import InMemoryTaskStore
from users import User, UserManager

logger = get_logger("app_factory")


def build_user_manager(user_specs):
    """
    user_specs: iterable of dicts with keys name, quota
    """
    manager = UserManager()
    for spec in user_specs:
        manager.add_user(User(name=spec["name"], quota=spec["quota"]))
    return manager


def build_scheduler(
    task_dicts,
    user_specs,
    max_workers=MAX_WORKERS,
    batch_size=BATCH_SIZE,
):
    setup_logging()

    user_manager = build_user_manager(user_specs)
    task_store = InMemoryTaskStore()
    load_dicts_into_store(task_store, task_dicts)

    executor_registry = TaskExecutorRegistry(default=DefaultTaskExecutor())
    for action in ("sync", "backup", "delete"):
        executor_registry.register(action, DefaultTaskExecutor())
    scheduler = Scheduler(
        task_store,
        user_manager,
        executor_registry,
        max_workers=max_workers,
        batch_size=batch_size,
    )

    log_with_context(
        logger,
        logging.INFO,
        "Application initialized",
        users=len(user_specs),
        tasks=task_store.total_tasks,
        max_workers=max_workers,
        batch_size=batch_size,
    )
    return scheduler
