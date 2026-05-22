import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from edge_codes import EdgeCaseCode
from exceptions import UserNotFoundError, UserValidationError
from log_config import get_logger, log_with_context

logger = get_logger("users")


class RejectionCode(Enum):
    """User/quota reservation outcomes (maps to EdgeCaseCode values)."""

    NONE = EdgeCaseCode.NONE
    UNKNOWN_USER = EdgeCaseCode.UNKNOWN_USER
    ZERO_QUOTA = EdgeCaseCode.ZERO_QUOTA
    QUOTA_EXCEEDED = EdgeCaseCode.QUOTA_EXCEEDED
    QUOTA_OVERFLOW = EdgeCaseCode.QUOTA_OVERFLOW


@dataclass
class ExecutionReservation:
    """Result of attempting to reserve quota for a task."""

    reserved: bool
    code: RejectionCode = RejectionCode.NONE
    message: str = ""

    @property
    def rejected(self):
        return not self.reserved


@dataclass
class User:
    name: str
    quota: int
    executed: int = 0
    active_tasks: int = 0

    def __post_init__(self):
        validate_quota(self.quota, self.name)

    @property
    def remaining_quota(self):
        return max(0, self.quota - self.executed)

    def has_quota_remaining(self):
        return self.executed < self.quota


def validate_quota(quota, username=None):
    if quota < 0:
        raise UserValidationError(
            "User quota must be >= 0 (got {}).".format(quota),
            username=username,
        )


class UserManager:
    def __init__(self, users=None):
        self._users = {}  # type: Dict[str, User]
        self._user_locks = {}  # type: Dict[str, threading.Lock]
        self._locks_guard = threading.Lock()
        if users:
            for user in users.values():
                self.add_user(user)

    def _lock_for(self, username):
        with self._locks_guard:
            if username not in self._user_locks:
                self._user_locks[username] = threading.Lock()
            return self._user_locks[username]

    def add_user(self, user):
        validate_quota(user.quota, user.name)
        with self._lock_for(user.name):
            self._users[user.name] = user
            log_with_context(
                logger,
                logging.DEBUG,
                "User registered",
                user=user.name,
                quota=user.quota,
            )

    def get_user(self, name):
        with self._lock_for(name):
            return self._users.get(name)

    def get_rejection(self, username):
        """Inspect why a user cannot run without reserving quota."""
        lock = self._lock_for(username)
        with lock:
            return self._check_reservation(username)

    def reserve_execution(self, username):
        lock = self._lock_for(username)
        with lock:
            rejection = self._check_reservation(username)
            if rejection.rejected:
                return rejection
            user = self._users[username]
            user.executed += 1
            user.active_tasks += 1
            log_with_context(
                logger,
                logging.DEBUG,
                "Execution reserved",
                user=username,
                executed=user.executed,
                quota=user.quota,
                active=user.active_tasks,
            )
            return ExecutionReservation(reserved=True)

    def _check_reservation(self, username):
        user = self._users.get(username)
        if user is None:
            return ExecutionReservation(
                reserved=False,
                code=RejectionCode.UNKNOWN_USER,
                message="Unknown user: {}".format(username),
            )
        if user.quota == 0:
            return ExecutionReservation(
                reserved=False,
                code=RejectionCode.ZERO_QUOTA,
                message="User {} has zero quota and cannot run tasks.".format(
                    username
                ),
            )
        if user.executed > user.quota:
            log_with_context(
                logger,
                logging.ERROR,
                "Quota overflow detected",
                user=username,
                executed=user.executed,
                quota=user.quota,
            )
            return ExecutionReservation(
                reserved=False,
                code=RejectionCode.QUOTA_OVERFLOW,
                message="User {} quota overflow ({}/{} executed).".format(
                    username, user.executed, user.quota
                ),
            )
        if not user.has_quota_remaining():
            return ExecutionReservation(
                reserved=False,
                code=RejectionCode.QUOTA_EXCEEDED,
                message="User {} has exceeded quota ({}/{}).".format(
                    username, user.executed, user.quota
                ),
            )
        return ExecutionReservation(reserved=True)

    def begin_execution(self, username):
        """Backward-compatible boolean API."""
        return self.reserve_execution(username).reserved

    def rejection_reason(self, username):
        return self.get_rejection(username).message

    def end_execution(self, username):
        lock = self._lock_for(username)
        with lock:
            user = self._users.get(username)
            if user is None:
                raise UserNotFoundError(username)
            user.active_tasks = max(0, user.active_tasks - 1)
            log_with_context(
                logger,
                logging.DEBUG,
                "Execution ended",
                user=username,
                active=user.active_tasks,
            )

    def release_quota(self, username):
        lock = self._lock_for(username)
        with lock:
            user = self._users.get(username)
            if user is None:
                raise UserNotFoundError(username)
            user.executed = max(0, user.executed - 1)
            log_with_context(
                logger,
                logging.DEBUG,
                "Quota released",
                user=username,
                executed=user.executed,
                quota=user.quota,
            )

    def quota_exceeded_message(self, username):
        return self.get_rejection(username).message
