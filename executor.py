import logging
from abc import ABC, abstractmethod

from config import LOG_PER_TASK_AT_INFO
from exceptions import TaskExecutionError
from log_config import get_logger, log_with_context
from models import Task

logger = get_logger("executor")


class TaskExecutor(ABC):
    @abstractmethod
    def execute(self, task):
        pass


class DefaultTaskExecutor(TaskExecutor):
    def execute(self, task):
        level = logging.INFO if LOG_PER_TASK_AT_INFO else logging.DEBUG
        log_with_context(
            logger,
            level,
            "Task executed",
            task_id=task.task_id,
            user=task.user,
            action=task.action,
            target=task.target,
        )


class TaskExecutorRegistry:
    def __init__(self, default=None, strict_unknown=None):
        from config import STRICT_UNKNOWN_ACTIONS

        self._executors = {}
        self._default = default or DefaultTaskExecutor()
        self._strict_unknown = (
            STRICT_UNKNOWN_ACTIONS if strict_unknown is None else strict_unknown
        )

    @property
    def strict_unknown(self):
        return self._strict_unknown

    def register(self, action, executor):
        self._executors[action] = executor
        logger.debug("Registered executor for action=%s", action)

    def is_registered(self, action):
        return action in self._executors

    def registered_actions(self):
        return list(self._executors.keys())

    def get_executor(self, action):
        return self._executors.get(action, self._default)

    def execute(self, task):
        log_with_context(
            logger,
            logging.DEBUG,
            "Dispatching task",
            task_id=task.task_id,
            action=task.action,
        )
        try:
            self.get_executor(task.action).execute(task)
        except TaskExecutionError:
            raise
        except Exception as exc:
            raise TaskExecutionError(
                "Executor failed for action '{}'.".format(task.action),
                task_id=task.task_id,
                user=task.user,
                action=task.action,
                cause=exc,
            )
