import threading
import unittest

from exceptions import UserNotFoundError, UserValidationError
from users import User, UserManager


class TestUser(unittest.TestCase):
    def test_remaining_quota_never_negative(self):
        user = User(name="a", quota=2, executed=5)
        self.assertEqual(user.remaining_quota, 0)

    def test_has_quota_when_executed_equals_quota(self):
        user = User(name="a", quota=2, executed=2)
        self.assertFalse(user.has_quota_remaining())

    def test_zero_quota_never_executes(self):
        user = User(name="a", quota=0)
        self.assertFalse(user.has_quota_remaining())


class TestUserManager(unittest.TestCase):
    def setUp(self):
        self.manager = UserManager(
            {"alice": User(name="alice", quota=2), "bob": User(name="bob", quota=5)}
        )

    def test_begin_and_end_execution(self):
        self.assertTrue(self.manager.begin_execution("alice"))
        alice = self.manager.get_user("alice")
        self.assertEqual(alice.executed, 1)
        self.assertEqual(alice.active_tasks, 1)
        self.manager.end_execution("alice")
        self.assertEqual(alice.active_tasks, 0)
        self.assertEqual(alice.executed, 1)

    def test_quota_blocks_third_execution(self):
        self.assertTrue(self.manager.begin_execution("alice"))
        self.manager.end_execution("alice")
        self.assertTrue(self.manager.begin_execution("alice"))
        self.manager.end_execution("alice")
        self.assertFalse(self.manager.begin_execution("alice"))

    def test_unknown_user_begin_returns_false(self):
        self.assertFalse(self.manager.begin_execution("ghost"))

    def test_unknown_user_rejection_reason(self):
        self.assertIn("Unknown user", self.manager.rejection_reason("ghost"))

    def test_zero_quota_rejection_code(self):
        manager = UserManager({"z": User(name="z", quota=0)})
        self.assertEqual(
            manager.get_rejection("z").code.value, "ZERO_QUOTA"
        )

    def test_quota_exceeded_rejection_reason(self):
        user = self.manager.get_user("alice")
        user.executed = user.quota
        self.assertIn("exceeded quota", self.manager.rejection_reason("alice"))

    def test_end_execution_unknown_raises(self):
        with self.assertRaises(UserNotFoundError):
            self.manager.end_execution("ghost")

    def test_negative_quota_raises_on_user_create(self):
        with self.assertRaises(UserValidationError):
            User(name="bad", quota=-1)

    def test_release_quota_after_failure(self):
        self.assertTrue(self.manager.begin_execution("alice"))
        self.manager.release_quota("alice")
        alice = self.manager.get_user("alice")
        self.assertEqual(alice.executed, 0)

    def test_concurrent_same_user_respects_quota(self):
        manager = UserManager({"alice": User(name="alice", quota=1)})
        successes = []

        def worker():
            if manager.begin_execution("alice"):
                successes.append(1)
                manager.end_execution("alice")

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 1)
        self.assertEqual(manager.get_user("alice").executed, 1)


if __name__ == "__main__":
    unittest.main()
