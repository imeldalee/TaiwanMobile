import logging
import sys

from app_factory import build_scheduler
from config import BATCH_SIZE, MAX_WORKERS
from exceptions import TaskLoadError, TaskSchedulerError, UserValidationError
from log_config import get_logger, setup_logging

logger = get_logger("main")


def sample_task_dicts():
    return [
        {
            "user": "alice",
            "time": "12:00",
            "action": "sync",
            "target": "/data/x",
            "retries": 2,
        },
        {
            "user": "bob",
            "time": "12:00",
            "action": "backup",
            "params": {"target": "/srv/y", "compress": True},
        },
        {
            "user": "alice",
            "time": "12:00",
            "action": "delete",
            "target": "/tmp/z",
            "force": True,
        },
    ]


def sample_user_specs():
    return [
        {"name": "alice", "quota": 3},
        {"name": "bob", "quota": 5},
    ]


def build_app(max_workers=MAX_WORKERS, batch_size=BATCH_SIZE):
    return build_scheduler(
        sample_task_dicts(),
        sample_user_specs(),
        max_workers=max_workers,
        batch_size=batch_size,
    )


def run():
    setup_logging()
    try:
        scheduler = build_app()
        scheduler.run_once()
    except TaskSchedulerError as exc:
        logger.error("[%s] %s", exc.code, exc.message)
        sys.exit(1)
    except Exception:
        logger.exception("Unhandled application error")
        sys.exit(1)


if __name__ == "__main__":
    run()
