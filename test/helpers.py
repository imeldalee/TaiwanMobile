from executor import TaskExecutor


class CountingExecutor(TaskExecutor):
    def __init__(self):
        self.executed_ids = []
        self.fail_on = set()

    def execute(self, task):
        if task.task_id in self.fail_on:
            raise ValueError("task failed")
        self.executed_ids.append(task.task_id)
