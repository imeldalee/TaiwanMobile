"""Single-task execution lifecycle — separated from scheduling orchestration."""

import logging

from edge_codes import EdgeCaseCode
from exceptions import TaskExecutionError
from executor import TaskExecutorRegistry
from log_config import get_logger, log_with_context
from models import Task
from users import UserManager
from validation import validate_task_for_execution

logger = get_logger("execution")


class TaskRunOutcome(object):
    __slots__ = ("status", "task_id", "user", "code", "message")

    STATUS_EXECUTED = "executed"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    def __init__(self, status, task, code="", message=""):
        self.status = status
        self.task_id = task.task_id
        self.user = task.user
        self.code = code
        self.message = message


class TaskRunner(object):
    def __init__(self, user_manager, executor_registry):
        self._user_manager = user_manager  # type: UserManager
        self._executor_registry = executor_registry  # type: TaskExecutorRegistry

    def _skip(self, task, code, message):
        log_with_context(
            logger,
            logging.WARNING,
            "Task skipped",
            task_id=task.task_id,
            user=task.user,
            action=task.action,
            code=code,
            reason=message,
        )
        return TaskRunOutcome(
            TaskRunOutcome.STATUS_SKIPPED,
            task,
            code=code,
            message=message,
        )

    def run(self, task, time_slot=None):
        """
        Validate, reserve quota, execute, and clean up.
        Returns a TaskRunOutcome; does not raise for expected edge cases.
        """
        precheck = validate_task_for_execution(
            task, time_slot, self._executor_registry
        )
        if precheck.failed:
            return self._skip(task, precheck.code, precheck.message)

        reservation = self._user_manager.reserve_execution(task.user)
        if reservation.rejected:
            return self._skip(
                task,
                reservation.code.value,
                reservation.message,
            )

        failed = False
        error_message = ""
        try:
            self._executor_registry.execute(task)
            log_with_context(
                logger,
                logging.DEBUG,
                "Task completed",
                task_id=task.task_id,
                user=task.user,
                action=task.action,
            )
            return TaskRunOutcome(TaskRunOutcome.STATUS_EXECUTED, task)
        except TaskExecutionError as exc:
            failed = True
            error_message = str(exc)
            log_with_context(
                logger,
                logging.ERROR,
                "Task execution failed",
                task_id=task.task_id,
                user=task.user,
                action=task.action,
                code=exc.code,
                error=error_message,
            )
            logger.exception("Trace for task_id=%s", task.task_id)
            return TaskRunOutcome(
                TaskRunOutcome.STATUS_FAILED,
                task,
                code=exc.code,
                message=error_message,
            )
        except Exception as exc:
            failed = True
            error_message = str(exc)
            log_with_context(
                logger,
                logging.ERROR,
                "Unexpected task failure",
                task_id=task.task_id,
                user=task.user,
                action=task.action,
                error=error_message,
            )
            logger.exception("Trace for task_id=%s", task.task_id)
            return TaskRunOutcome(
                TaskRunOutcome.STATUS_FAILED,
                task,
                code="UNEXPECTED_ERROR",
                message=error_message,
            )
        finally:
            self._user_manager.end_execution(task.user)
            if failed:
                self._user_manager.release_quota(task.user)
