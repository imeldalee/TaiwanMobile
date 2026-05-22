import unittest

from execution import TaskRunner, TaskRunOutcome
from executor import TaskExecutorRegistry
from models import Task
from tests.helpers import CountingExecutor
from users import RejectionCode, User, UserManager


class TestTaskRunner(unittest.TestCase):
    def setUp(self):
        self.executor = CountingExecutor()
        self.registry = TaskExecutorRegistry(
            default=self.executor, strict_unknown=False
        )
        self.users = UserManager()
        self.users.add_user(User(name="alice", quota=2))
        self.runner = TaskRunner(self.users, self.registry)

    def test_executed_outcome(self):
        task = Task(user="alice", time="12:00", action="x", task_id="t1")
        outcome = self.runner.run(task)
        self.assertEqual(outcome.status, TaskRunOutcome.STATUS_EXECUTED)
        self.assertEqual(self.executor.executed_ids, ["t1"])

    def test_skipped_unknown_user(self):
        task = Task(user="ghost", time="12:00", action="x", task_id="t1")
        outcome = self.runner.run(task)
        self.assertEqual(outcome.status, TaskRunOutcome.STATUS_SKIPPED)
        self.assertEqual(outcome.code, RejectionCode.UNKNOWN_USER.value)

    def test_failed_releases_quota(self):
        task = Task(user="alice", time="12:00", action="x", task_id="fail")
        self.executor.fail_on.add("fail")
        self.runner.run(task)
        self.assertEqual(self.users.get_user("alice").executed, 0)


if __name__ == "__main__":
    unittest.main()
