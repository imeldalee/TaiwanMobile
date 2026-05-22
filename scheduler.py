import datetime
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import BATCH_SIZE, MAX_WORKERS
from execution import TaskRunner, TaskRunOutcome
from executor import TaskExecutorRegistry
from log_config import get_logger, log_with_context
from task_store import TaskStore
from users import UserManager

logger = get_logger("scheduler")


class RunStats(object):
    __slots__ = ("executed", "skipped", "failed", "users_due", "failures", "skip_reasons")

    def __init__(self):
        self.executed = 0
        self.skipped = 0
        self.failed = 0
        self.users_due = Counter()
        self.failures = []  # type: list
        self.skip_reasons = Counter()


class Scheduler(object):
    def __init__(
        self,
        task_store,
        user_manager,
        executor_registry,
        max_workers=MAX_WORKERS,
        batch_size=BATCH_SIZE,
        task_runner=None,
    ):
        self._task_store = task_store  # type: TaskStore
        self._user_manager = user_manager  # type: UserManager
        self._executor_registry = executor_registry  # type: TaskExecutorRegistry
        self._task_runner = task_runner or TaskRunner(
            user_manager, executor_registry
        )
        self._max_workers = max(1, max_workers)
        self._batch_size = max(1, batch_size)

    def current_time(self):
        return datetime.datetime.now().strftime("%H:%M")

    def _record_outcome(self, outcome, stats):
        if outcome.status == TaskRunOutcome.STATUS_EXECUTED:
            stats.executed += 1
        elif outcome.status == TaskRunOutcome.STATUS_SKIPPED:
            stats.skipped += 1
            if outcome.code:
                stats.skip_reasons[outcome.code] += 1
        else:
            stats.failed += 1
            stats.failures.append(outcome)

    def _run_task(self, task, stats, time_slot):
        outcome = self._task_runner.run(task, time_slot=time_slot)
        self._record_outcome(outcome, stats)

    def _process_batch(self, batch, stats, parallel, time_slot):
        stats.users_due.update(task.user for task in batch)
        if parallel and len(batch) > 1:
            workers = min(self._max_workers, len(batch))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(self._run_task, task, stats, time_slot)
                    for task in batch
                ]
                for future in as_completed(futures):
                    future.result()
        else:
            for task in batch:
                self._run_task(task, stats, time_slot)

    def run_once(self, time=None, parallel=True):
        slot = time if time is not None else self.current_time()
        due_count = self._task_store.due_count(slot)
        if due_count == 0:
            logger.debug("No tasks due at time_slot=%s", slot)
            return RunStats()

        stats = RunStats()
        log_with_context(
            logger,
            logging.INFO,
            "Scheduler tick started",
            time_slot=slot,
            due_count=due_count,
            batch_size=self._batch_size,
            max_workers=self._max_workers,
            parallel=parallel,
        )

        for batch_index, batch in enumerate(
            self._task_store.iter_due_batches(slot, self._batch_size)
        ):
            logger.debug(
                "Processing batch index=%d size=%d time_slot=%s",
                batch_index,
                len(batch),
                slot,
            )
            self._process_batch(batch, stats, parallel, slot)

        simultaneous_users = sum(
            1 for _user, count in stats.users_due.items() if count > 1
        )
        log_with_context(
            logger,
            logging.INFO,
            "Scheduler tick complete",
            time_slot=slot,
            executed=stats.executed,
            skipped=stats.skipped,
            failed=stats.failed,
            simultaneous_users=simultaneous_users,
        )
        if stats.skip_reasons:
            log_with_context(
                logger,
                logging.INFO,
                "Skip breakdown",
                time_slot=slot,
                **dict(stats.skip_reasons),
            )
        if stats.failures:
            logger.warning(
                "Tick had %d failure(s); see ERROR logs above for task_id trace",
                len(stats.failures),
            )
        return stats
