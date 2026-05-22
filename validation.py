"""Pre-execution validation for task edge cases."""

from config import ACTION_REQUIRED_PARAMS
from edge_codes import EdgeCaseCode
from log_config import get_logger

logger = get_logger("validation")


class ValidationResult(object):
    __slots__ = ("ok", "code", "message")

    def __init__(self, ok, code=EdgeCaseCode.NONE, message=""):
        self.ok = ok
        self.code = code
        self.message = message

    @property
    def failed(self):
        return not self.ok


def validate_time_slot_match(task, scheduler_slot):
    if scheduler_slot is None:
        return ValidationResult(True)
    if task.time != scheduler_slot:
        return ValidationResult(
            False,
            EdgeCaseCode.TIME_MISMATCH,
            "Task time '{}' does not match scheduler slot '{}'.".format(
                task.time, scheduler_slot
            ),
        )
    return ValidationResult(True)


def validate_required_parameters(task):
    required = ACTION_REQUIRED_PARAMS.get(task.action, [])
    if not required:
        return ValidationResult(True)

    missing = []
    for key in required:
        if key not in task.params:
            missing.append(key)
            continue
        value = task.params[key]
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)

    if missing:
        return ValidationResult(
            False,
            EdgeCaseCode.MISSING_PARAMETERS,
            "Task action '{}' missing required parameter(s): {}.".format(
                task.action, missing
            ),
        )
    return ValidationResult(True)


def validate_known_action(task, executor_registry):
    if not executor_registry.strict_unknown:
        return ValidationResult(True)
    if executor_registry.is_registered(task.action):
        return ValidationResult(True)
    return ValidationResult(
        False,
        EdgeCaseCode.UNKNOWN_ACTION,
        "No executor registered for action '{}'.".format(task.action),
    )


def validate_task_for_execution(task, scheduler_slot, executor_registry):
    """Run all pre-execution checks in a fixed order."""
    checks = (
        lambda: validate_time_slot_match(task, scheduler_slot),
        lambda: validate_required_parameters(task),
        lambda: validate_known_action(task, executor_registry),
    )
    for check in checks:
        result = check()
        if result.failed:
            logger.debug(
                "Pre-execution check failed code=%s task_id=%s",
                result.code,
                task.task_id,
            )
            return result
    return ValidationResult(True)
