from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import todoist


@dataclass
class TodoistHelper:
    connection: Any = field(init=False)
    token_str: str

    def __post_init__(self):
        with open(self.token_str, "r") as f:
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
        return None

    def get_section_id(self, desired_section):
        for project in self.connection.state["sections"]:
            if desired_section == project.data.get("name"):
                return project.data.get("id")
        return None

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

    def add_item_to_project(self, item, project, section=None):
        project_id = self.get_project_id(project)
        assert project_id is not None, "Id of project {:s} could not be found!".format(
            project
        )
        section_id = None
        if section is not None:
            section_id = self.get_section_id(section)
            assert (
                    section_id is not None
            ), "Id of section {:s} could not be found!".format(section)
        new_item = self.connection.add_item(
            item, project_id=project_id, section_id=section_id
        )
        # somehow, the section is not correctly set with the previous command
        if section_id is not None:
            self.connection.items.move(new_item["id"], section_id=section_id)

        self.connection.commit()

    def get_all_items_in_project(self, project):
        items = []
        project_id = self.get_project_id(project)
        assert project_id is not None, "Id of project {:s} could not be found!".format(
            project
        )
        for item in self.connection.state["items"]:
            if item["project_id"] == project_id:
                items.append(item)
        return items

    def delete_all_items_in_project(self, project, no_recurring=True):
        """
        Deletes items in project "project" that fulfil specified properties.
        :param project: string, name of project.
        :param no_recurring: boolean. If true, do not delete recurring items from list.
        """
        project_id = self.get_project_id(project)

        for task in self.connection.state["items"]:
            if task["project_id"] == project_id:
                if no_recurring:
                    if task["due"] is not None:
                        if task["due"]["is_recurring"] is True or task["due"]["date"] is not None:
                            continue
                self.connection.items.delete(task["id"])

        self.connection.commit()
