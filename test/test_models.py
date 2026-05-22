import unittest

from exceptions import TaskValidationError
from models import Task


class TestTask(unittest.TestCase):
    def test_from_dict_flat_extra_params(self):
        task = Task.from_dict(
            {
                "user": "alice",
                "time": "09:00",
                "action": "sync",
                "target": "/data",
                "retries": 3,
            }
        )
        self.assertEqual(task.user, "alice")
        self.assertEqual(task.target, "/data")
        self.assertEqual(task.get_param("retries"), 3)

    def test_from_dict_nested_params_merged(self):
        task = Task.from_dict(
            {
                "user": "bob",
                "time": "10:00",
                "action": "backup",
                "params": {"target": "/srv", "compress": True},
                "priority": "high",
            }
        )
        self.assertEqual(task.params["target"], "/srv")
        self.assertTrue(task.params["compress"])
        self.assertEqual(task.params["priority"], "high")

    def test_from_dict_preserves_task_id(self):
        task = Task.from_dict(
            {
                "user": "u",
                "time": "11:00",
                "action": "x",
                "task_id": "fixed-id",
            }
        )
        self.assertEqual(task.task_id, "fixed-id")

    def test_from_dict_missing_required_raises(self):
        with self.assertRaises(TaskValidationError) as ctx:
            Task.from_dict({"user": "a", "time": "12:00"})
        self.assertIn("action", str(ctx.exception))

    def test_invalid_time_slot_raises(self):
        with self.assertRaises(TaskValidationError):
            Task.from_dict({"user": "a", "time": "25:99", "action": "x"})

    def test_target_empty_when_missing(self):
        task = Task(user="u", time="12:00", action="noop")
        self.assertEqual(task.target, "")

    def test_unique_task_ids_by_default(self):
        a = Task(user="u", time="12:00", action="a")
        b = Task(user="u", time="12:00", action="b")
        self.assertNotEqual(a.task_id, b.task_id)

    def test_get_param_default(self):
        task = Task(user="u", time="12:00", action="a")
        self.assertIsNone(task.get_param("missing"))
        self.assertEqual(task.get_param("missing", "x"), "x")


if __name__ == "__main__":
    unittest.main()
