import unittest
from unittest.mock import patch

from executor import TaskExecutorRegistry
from models import Task
from scheduler import Scheduler
from task_store import InMemoryTaskStore
from tests.helpers import CountingExecutor
from users import User, UserManager


def make_scheduler(tasks, users, max_workers=4, batch_size=2):
    store = InMemoryTaskStore()
    store.add_many(tasks)
    user_manager = UserManager(users)
    executor = CountingExecutor()
    registry = TaskExecutorRegistry(default=executor, strict_unknown=False)
    for task in tasks:
        if not registry.is_registered(task.action):
            registry.register(task.action, executor)
    sched = Scheduler(
        store,
        user_manager,
        registry,
        max_workers=max_workers,
        batch_size=batch_size,
    )
    return sched, executor, user_manager


class TestScheduler(unittest.TestCase):
    def test_no_tasks_due_does_nothing(self):
        sched, executor, _ = make_scheduler(
            [Task(user="a", time="12:00", action="x")],
            {"a": User(name="a", quota=1)},
        )
        sched.run_once("99:99")
        self.assertEqual(executor.executed_ids, [])

    def test_executes_all_due_within_quota(self):
        tasks = [
            Task(user="alice", time="12:00", action="a", task_id="t1"),
            Task(user="alice", time="12:00", action="b", task_id="t2"),
        ]
        sched, executor, um = make_scheduler(tasks, {"alice": User(name="alice", quota=3)})
        sched.run_once("12:00", parallel=False)
        self.assertEqual(set(executor.executed_ids), {"t1", "t2"})
        self.assertEqual(um.get_user("alice").executed, 2)

    def test_skips_tasks_when_quota_exceeded(self):
        tasks = [
            Task(user="alice", time="12:00", action="a", task_id="t1"),
            Task(user="alice", time="12:00", action="b", task_id="t2"),
            Task(user="alice", time="12:00", action="c", task_id="t3"),
        ]
        sched, executor, um = make_scheduler(
            tasks, {"alice": User(name="alice", quota=2)}
        )
        sched.run_once("12:00", parallel=False)
        self.assertEqual(len(executor.executed_ids), 2)
        self.assertEqual(um.get_user("alice").executed, 2)

    def test_unknown_user_skipped_not_executed(self):
        sched, executor, _ = make_scheduler(
            [Task(user="ghost", time="12:00", action="x", task_id="t1")],
            {"alice": User(name="alice", quota=5)},
        )
        sched.run_once("12:00", parallel=False)
        self.assertEqual(executor.executed_ids, [])

    def test_failed_task_does_not_consume_quota(self):
        tasks = [Task(user="alice", time="12:00", action="x", task_id="fail-me")]
        sched, executor, um = make_scheduler(
            tasks, {"alice": User(name="alice", quota=2)}
        )
        executor.fail_on.add("fail-me")
        sched.run_once("12:00", parallel=False)
        self.assertEqual(executor.executed_ids, [])
        self.assertEqual(um.get_user("alice").executed, 0)

    def test_after_failure_quota_available_for_next_task(self):
        tasks = [
            Task(user="alice", time="12:00", action="x", task_id="fail-me"),
            Task(user="alice", time="12:00", action="y", task_id="ok"),
        ]
        sched, executor, um = make_scheduler(
            tasks, {"alice": User(name="alice", quota=1)}
        )
        executor.fail_on.add("fail-me")
        sched.run_once("12:00", parallel=False)
        self.assertEqual(executor.executed_ids, ["ok"])
        self.assertEqual(um.get_user("alice").executed, 1)

    def test_parallel_same_user_quota_one_only_runs_one(self):
        tasks = [
            Task(user="alice", time="12:00", action="a", task_id="t1"),
            Task(user="alice", time="12:00", action="b", task_id="t2"),
        ]
        sched, executor, _ = make_scheduler(
            tasks, {"alice": User(name="alice", quota=1)}, max_workers=8
        )
        sched.run_once("12:00", parallel=True)
        self.assertEqual(len(executor.executed_ids), 1)

    def test_batching_processes_all_batches(self):
        tasks = [
            Task(user="bob", time="08:00", action="a", task_id="t%d" % i)
            for i in range(5)
        ]
        sched, executor, um = make_scheduler(
            tasks, {"bob": User(name="bob", quota=10)}, batch_size=2
        )
        sched.run_once("08:00", parallel=False)
        self.assertEqual(len(executor.executed_ids), 5)

    def test_max_workers_zero_clamped_to_one(self):
        sched, _, _ = make_scheduler([], {}, max_workers=0)
        self.assertEqual(sched._max_workers, 1)

    @patch("scheduler.datetime")
    def test_run_once_uses_current_time_when_none(self, mock_dt):
        mock_dt.datetime.now.return_value.strftime.return_value = "15:30"
        sched, executor, _ = make_scheduler(
            [Task(user="a", time="15:30", action="x", task_id="t1")],
            {"a": User(name="a", quota=1)},
        )
        sched.run_once()
        self.assertEqual(executor.executed_ids, ["t1"])


if __name__ == "__main__":
    unittest.main()
