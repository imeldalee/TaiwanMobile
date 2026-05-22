import unittest

from models import Task
from task_loader import load_dicts_into_store
from task_store import InMemoryTaskStore


class TestInMemoryTaskStore(unittest.TestCase):
    def test_empty_slot_returns_zero_due(self):
        store = InMemoryTaskStore()
        self.assertEqual(store.due_count("99:99"), 0)
        self.assertEqual(list(store.iter_due_batches("99:99", 10)), [])

    def test_indexed_by_time_slot(self):
        store = InMemoryTaskStore()
        store.add(Task(user="a", time="12:00", action="x"))
        store.add(Task(user="b", time="13:00", action="y"))
        self.assertEqual(store.due_count("12:00"), 1)
        self.assertEqual(store.total_tasks, 2)

    def test_iter_due_batches_splits_correctly(self):
        store = InMemoryTaskStore()
        for i in range(5):
            store.add(Task(user="u", time="12:00", action="a"))
        batches = list(store.iter_due_batches("12:00", batch_size=2))
        self.assertEqual([len(b) for b in batches], [2, 2, 1])

    def test_iter_due_batches_invalid_batch_size_coerced(self):
        store = InMemoryTaskStore()
        store.add(Task(user="u", time="12:00", action="a"))
        batches = list(store.iter_due_batches("12:00", batch_size=0))
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 1)

    def test_add_many(self):
        store = InMemoryTaskStore()
        tasks = [Task(user="u", time="08:00", action="a") for _ in range(3)]
        store.add_many(tasks)
        self.assertEqual(store.due_count("08:00"), 3)


class TestLoadDictsIntoStore(unittest.TestCase):
    def test_empty_iterator_returns_zero(self):
        store = InMemoryTaskStore()
        self.assertEqual(load_dicts_into_store(store, []), 0)
        self.assertEqual(store.total_tasks, 0)

    def test_chunked_load(self):
        store = InMemoryTaskStore()
        dicts = [
            {"user": "u", "time": "12:00", "action": "sync", "target": "/x"}
            for _ in range(5)
        ]
        loaded = load_dicts_into_store(store, dicts, parse_batch_size=2)
        self.assertEqual(loaded, 5)
        self.assertEqual(store.due_count("12:00"), 5)


if __name__ == "__main__":
    unittest.main()
