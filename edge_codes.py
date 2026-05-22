"""
Canonical string codes for edge-case outcomes.
Used consistently in logs, RunStats.skip_reasons, and unit tests.
"""


class EdgeCaseCode(object):
    # No issue
    NONE = "NONE"

    # User / quota edge cases (see users.UserManager._check_reservation)
    ZERO_QUOTA = "ZERO_QUOTA"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    QUOTA_OVERFLOW = "QUOTA_OVERFLOW"

    # Task validation edge cases (see validation.py)
    TIME_MISMATCH = "TIME_MISMATCH"
    UNKNOWN_USER = "UNKNOWN_USER"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    MISSING_PARAMETERS = "MISSING_PARAMETERS"
