import unittest

from edge_codes import EdgeCaseCode
from exceptions import TaskLoadError, TaskValidationError, UserValidationError
from execution import TaskRunner
from executor import DefaultTaskExecutor, TaskExecutorRegistry
from models import Task
from scheduler import Scheduler
from task_loader import load_dicts_into_store
from task_store import InMemoryTaskStore
from tests.helpers import CountingExecutor
from users import RejectionCode, User, UserManager
from validation import (
    validate_known_action,
    validate_required_parameters,
    validate_time_slot_match,
)


def make_runner(users, strict=True, register_actions=True):
    registry = TaskExecutorRegistry(
        default=CountingExecutor(), strict_unknown=strict
    )
    if register_actions:
        registry.register("sync", CountingExecutor())
    return TaskRunner(UserManager(users), registry)


class TestZeroQuota(unittest.TestCase):
    def test_reserve_rejects_zero_quota(self):
        manager = UserManager({"a": User(name="a", quota=0)})
        result = manager.get_rejection("a")
        self.assertEqual(result.code, RejectionCode.ZERO_QUOTA)
        self.assertIn("zero quota", result.message.lower())

    def test_runner_skips_zero_quota_user(self):
        runner = make_runner({"a": User(name="a", quota=0)})
        task = Task(user="a", time="12:00", action="sync", params={"target": "/x"})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.ZERO_QUOTA)


class TestQuotaOverflow(unittest.TestCase):
    def test_reserve_rejects_when_executed_above_quota(self):
        user = User(name="a", quota=2, executed=3)
        manager = UserManager({"a": user})
        result = manager.get_rejection("a")
        self.assertEqual(result.code, RejectionCode.QUOTA_OVERFLOW)

    def test_quota_exceeded_when_at_limit(self):
        user = User(name="a", quota=2, executed=2)
        manager = UserManager({"a": user})
        result = manager.get_rejection("a")
        self.assertEqual(result.code, RejectionCode.QUOTA_EXCEEDED)

    def test_scheduler_skips_overflow_tasks(self):
        store = InMemoryTaskStore()
        store.add(
            Task(user="a", time="12:00", action="sync", params={"target": "/x"}, task_id="t1")
        )
        user = User(name="a", quota=1, executed=2)
        registry = TaskExecutorRegistry(default=CountingExecutor())
        registry.register("sync", CountingExecutor())
        sched = Scheduler(store, UserManager({"a": user}), registry, batch_size=10)
        stats = sched.run_once("12:00", parallel=False)
        self.assertEqual(stats.executed, 0)
        self.assertEqual(stats.skip_reasons[EdgeCaseCode.QUOTA_OVERFLOW], 1)


class TestTimeMismatch(unittest.TestCase):
    def test_validate_time_mismatch(self):
        task = Task(user="a", time="10:00", action="sync", params={"target": "/x"})
        result = validate_time_slot_match(task, "12:00")
        self.assertEqual(result.code, EdgeCaseCode.TIME_MISMATCH)

    def test_runner_skips_mismatched_time(self):
        runner = make_runner({"a": User(name="a", quota=5)})
        task = Task(user="a", time="10:00", action="sync", params={"target": "/x"})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.TIME_MISMATCH)

    def test_scheduler_only_runs_matching_slot(self):
        store = InMemoryTaskStore()
        store.add(
            Task(user="a", time="10:00", action="sync", params={"target": "/x"}, task_id="t1")
        )
        store.add(
            Task(user="a", time="12:00", action="sync", params={"target": "/y"}, task_id="t2")
        )
        registry = TaskExecutorRegistry(default=CountingExecutor())
        registry.register("sync", CountingExecutor())
        sched = Scheduler(
            store, UserManager({"a": User(name="a", quota=5)}), registry
        )
        stats = sched.run_once("12:00", parallel=False)
        self.assertEqual(stats.executed, 1)


class TestUnknownUser(unittest.TestCase):
    def test_unknown_user_rejection(self):
        manager = UserManager()
        result = manager.get_rejection("ghost")
        self.assertEqual(result.code, RejectionCode.UNKNOWN_USER)

    def test_runner_skips_unknown_user(self):
        runner = make_runner({})
        task = Task(user="ghost", time="12:00", action="sync", params={"target": "/x"})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.UNKNOWN_USER)


class TestUnknownAction(unittest.TestCase):
    def test_validate_unknown_action_strict(self):
        registry = TaskExecutorRegistry(strict_unknown=True)
        task = Task(user="a", time="12:00", action="nonexistent", params={"target": "/x"})
        result = validate_known_action(task, registry)
        self.assertEqual(result.code, EdgeCaseCode.UNKNOWN_ACTION)

    def test_runner_skips_unknown_action(self):
        runner = make_runner({"a": User(name="a", quota=5)}, register_actions=False)
        task = Task(user="a", time="12:00", action="alien", params={"target": "/x"})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.UNKNOWN_ACTION)


class TestMissingParameters(unittest.TestCase):
    def test_validate_missing_target(self):
        task = Task(user="a", time="12:00", action="sync", params={})
        result = validate_required_parameters(task)
        self.assertEqual(result.code, EdgeCaseCode.MISSING_PARAMETERS)
        self.assertIn("target", result.message)

    def test_from_dict_raises_when_required_params_missing(self):
        with self.assertRaises(TaskValidationError) as ctx:
            Task.from_dict({"user": "a", "time": "12:00", "action": "sync"})
        self.assertIn("target", str(ctx.exception))

    def test_runner_skips_empty_target(self):
        runner = make_runner({"a": User(name="a", quota=5)})
        task = Task(user="a", time="12:00", action="sync", params={"target": "  "})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.MISSING_PARAMETERS)

    def test_runner_skips_missing_param_at_runtime(self):
        runner = make_runner({"a": User(name="a", quota=5)})
        task = Task(user="a", time="12:00", action="backup", params={})
        outcome = runner.run(task, time_slot="12:00")
        self.assertEqual(outcome.code, EdgeCaseCode.MISSING_PARAMETERS)


class TestLoadAndOtherEdgeCases(unittest.TestCase):
    def test_negative_quota_rejected_at_user_creation(self):
        with self.assertRaises(UserValidationError):
            User(name="bad", quota=-1)

    def test_load_dicts_aborts_on_invalid_mid_stream(self):
        store = InMemoryTaskStore()
        dicts = [
            {"user": "u", "time": "12:00", "action": "sync", "target": "/x"},
            {"user": "u", "time": "12:00"},
        ]
        with self.assertRaises(TaskLoadError):
            load_dicts_into_store(store, dicts, parse_batch_size=10)
        self.assertEqual(store.total_tasks, 0)

    def test_scheduler_skip_breakdown_multiple_reasons(self):
        store = InMemoryTaskStore()
        store.add(
            Task(user="ghost", time="12:00", action="sync", params={"target": "/x"}, task_id="t1")
        )
        store.add(
            Task(user="a", time="12:00", action="sync", params={}, task_id="t2")
        )
        registry = TaskExecutorRegistry(default=CountingExecutor())
        registry.register("sync", CountingExecutor())
        sched = Scheduler(
            store, UserManager({"a": User(name="a", quota=1)}), registry
        )
        stats = sched.run_once("12:00", parallel=False)
        self.assertEqual(stats.skipped, 2)
        self.assertEqual(stats.skip_reasons[EdgeCaseCode.UNKNOWN_USER], 1)
        self.assertEqual(stats.skip_reasons[EdgeCaseCode.MISSING_PARAMETERS], 1)


if __name__ == "__main__":
    unittest.main()
