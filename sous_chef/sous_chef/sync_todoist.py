from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import todoist


@dataclass
class SyncTodoist:
    connection: Any = field(init=False)

    def __post_init__(self):
        with open("token.todoist", "r") as f:
            token = f.read().strip()
        self.connection = todoist.TodoistAPI(token)
        self.connection.sync()

    # TODO do we need this? or is commit sufficient?
    def sync(self):
        self.connection.sync()

    def get_project_id(self, desired_project):
        for project in self.connection.state["projects"]:
            if desired_project == project.data.get("name"):
                return project.data.get("id")

    # TODO implement
    def add_defrost_task_to_active_tasks(self):
        project_id = self.get_project_id("Active tasks")
        # add task with this project id to defrost meat the day before

    def retrieve_freezer(self):
        freezer_contents = defaultdict(list)
        for task in self.connection.state["items"]:
            if task["project_id"] in [self.get_project_id("Freezer")]:
                freezer_contents["title"].append(task["content"])
                # TODO implement type based on section name
                freezer_contents["type"].append("undefined")
        return pd.DataFrame(freezer_contents)


# tasks are listed in self.connection.state["items"]
# freezer project id = 2247094287
# active tasks project id = 2228326726

if __name__ == "__main__":
    print(SyncTodoist().retrieve_freezer())
