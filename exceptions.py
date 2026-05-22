"""
Domain exceptions for the task scheduler.
Each subclass sets a stable `code` string for logging and API responses.
All exceptions format as: [CODE] human-readable message
"""


# --- Base -----------------------------------------------------------------

class TaskSchedulerError(Exception):
    """Base exception for all scheduler errors."""

    def __init__(self, message, code=None):
        super(TaskSchedulerError, self).__init__(message)
        self.code = code or "SCHEDULER_ERROR"
        self.message = message

    def __str__(self):
        return "[{}] {}".format(self.code, self.message)


# --- Task data & loading ---------------------------------------------------

class TaskValidationError(TaskSchedulerError):
    """Invalid task dict, time slot, or required parameters."""

    def __init__(self, message, missing_fields=None):
        super(TaskValidationError, self).__init__(message, code="TASK_VALIDATION_ERROR")
        self.missing_fields = missing_fields or []


class TaskLoadError(TaskSchedulerError):
    """Bulk load aborted; `loaded_count` reflects tasks stored before failure."""

    def __init__(self, message, loaded_count=0, cause=None):
        super(TaskLoadError, self).__init__(message, code="TASK_LOAD_ERROR")
        self.loaded_count = loaded_count
        self.cause = cause


# --- Users -----------------------------------------------------------------

class UserValidationError(TaskSchedulerError):
    """Invalid user configuration (e.g. negative quota)."""

    def __init__(self, message, username=None):
        super(UserValidationError, self).__init__(message, code="USER_VALIDATION_ERROR")
        self.username = username


class UserNotFoundError(TaskSchedulerError):
    """Referenced username is not registered."""

    def __init__(self, username):
        super(UserNotFoundError, self).__init__(
            "Unknown user: {}".format(username),
            code="USER_NOT_FOUND",
        )
        self.username = username


class QuotaExceededError(TaskSchedulerError):
    """Raised when API needs an explicit exception (runtime uses reservations)."""

    def __init__(self, username, quota, executed):
        super(QuotaExceededError, self).__init__(
            "User {} has exceeded quota ({}/{} executed).".format(
                username, executed, quota
            ),
            code="QUOTA_EXCEEDED",
        )
        self.username = username
        self.quota = quota
        self.executed = executed


# --- Execution -------------------------------------------------------------

class TaskExecutionError(TaskSchedulerError):
    """Executor failed; includes task identity for tracing."""

    def __init__(self, message, task_id=None, user=None, action=None, cause=None):
        super(TaskExecutionError, self).__init__(message, code="TASK_EXECUTION_ERROR")
        self.task_id = task_id
        self.user = user
        self.action = action
        self.cause = cause
