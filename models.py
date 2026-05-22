import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping
from uuid import uuid4

from config import ACTION_REQUIRED_PARAMS
from exceptions import TaskValidationError
from log_config import get_logger

logger = get_logger("models")

TIME_SLOT_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
REQUIRED_FIELDS = ("user", "time", "action")


@dataclass
class Task:
    user: str
    time: str  # HH:MM
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        self._validate_instance()

    @property
    def target(self):
        return str(self.params.get("target", ""))

    def get_param(self, key, default=None):
        return self.params.get(key, default)

    def _validate_instance(self):
        if not self.user:
            raise TaskValidationError("Task user must not be empty.")
        if not self.action:
            raise TaskValidationError("Task action must not be empty.")
        validate_time_slot(self.time)

    @classmethod
    def from_dict(cls, data):
        """Build a task from a dictionary (flat or nested under ``params``)."""
        missing = [key for key in REQUIRED_FIELDS if key not in data]
        if missing:
            raise TaskValidationError(
                "Task dict missing required fields: {}".format(missing),
                missing_fields=missing,
            )

        time_slot = data["time"]
        validate_time_slot(time_slot)

        params = dict(data.get("params") or {})
        reserved = set(REQUIRED_FIELDS) | {"params", "task_id"}
        for key, value in data.items():
            if key not in reserved:
                params[key] = value

        kwargs = {
            "user": data["user"],
            "time": time_slot,
            "action": data["action"],
            "params": params,
        }
        if data.get("task_id") is not None:
            kwargs["task_id"] = data["task_id"]

        task = cls(**kwargs)
        from validation import validate_required_parameters

        param_check = validate_required_parameters(task)
        if param_check.failed:
            raise TaskValidationError(
                param_check.message,
                missing_fields=ACTION_REQUIRED_PARAMS.get(task.action, []),
            )

        logger.debug(
            "Parsed task task_id=%s user=%s action=%s time=%s",
            task.task_id,
            task.user,
            task.action,
            task.time,
        )
        return task


def validate_time_slot(time_slot):
    if not TIME_SLOT_PATTERN.match(time_slot):
        raise TaskValidationError(
            "Invalid time slot '{}'. Expected HH:MM format.".format(time_slot)
        )
