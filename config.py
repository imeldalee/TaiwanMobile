"""
Application-wide settings.
Tune these values for throughput, logging verbosity, and validation strictness.
"""

# --- Scheduler throughput (large datasets) ---
MAX_WORKERS = 64          # Upper bound on parallel threads per batch
BATCH_SIZE = 1000         # How many due tasks to process per inner loop
LOG_PER_TASK_AT_INFO = False  # True = one INFO line per task; False = DEBUG only

# --- Action validation ---
# When True, only explicitly registered actions may run (see executor registry).
STRICT_UNKNOWN_ACTIONS = True

# Required parameter keys per action (checked at load and before execution).
ACTION_REQUIRED_PARAMS = {
    "sync": ["target"],
    "backup": ["target"],
    "delete": ["target"],
}
