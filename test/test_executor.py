import unittest

from exceptions import TaskExecutionError
from executor import DefaultTaskExecutor, TaskExecutor, TaskExecutorRegistry
from models import Task


class RecordingExecutor(TaskExecutor):
    def __init__(self):
        self.calls = []

    def execute(self, task):
        self.calls.append(task.task_id)


class FailingExecutor(TaskExecutor):
    def execute(self, task):
        raise RuntimeError("boom")


class TestTaskExecutorRegistry(unittest.TestCase):
    def test_default_executor_used_for_unknown_action(self):
        registry = TaskExecutorRegistry()
        task = Task(user="u", time="12:00", action="unknown")
        registry.execute(task)

    def test_registered_executor_overrides_default(self):
        custom = RecordingExecutor()
        registry = TaskExecutorRegistry()
        registry.register("sync", custom)
        task = Task(user="u", time="12:00", action="sync")
        registry.execute(task)
        self.assertEqual(custom.calls, [task.task_id])

    def test_failing_executor_wraps_error(self):
        registry = TaskExecutorRegistry(default=FailingExecutor())
        with self.assertRaises(TaskExecutionError) as ctx:
            registry.execute(Task(user="u", time="12:00", action="x"))
        self.assertIsNotNone(ctx.exception.task_id)


class TestDefaultTaskExecutor(unittest.TestCase):
    def test_execute_does_not_raise(self):
        DefaultTaskExecutor().execute(
            Task(user="u", time="12:00", action="a", params={"target": "/t"})
        )


if __name__ == "__main__":
    unittest.main()
