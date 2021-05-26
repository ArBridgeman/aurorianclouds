from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import todoist


@dataclass
class TodoistHelper:
    connection: Any = field(init=False)
    token_str: str
    active_labels: dict = field(init=False)

    def __post_init__(self):
        with open(self.token_str, "r") as f:
            token = f.read().strip()
        self.connection = todoist.TodoistAPI(token)
        self.sync()
        self.active_labels = self.get_active_labels()

    def sync(self):
        self.connection.sync()

    def commit(self):
        self.connection.commit()

    def get_active_labels(self):
        ldict = {}
        for label in self.connection.labels.state["labels"]:
            ldict[label["name"]] = label["id"]
        return ldict

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

    # TODO implement defrost task uploader
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

    def get_label_id_or_add_new(self, label):
        if label in self.active_labels.keys():
            return self.active_labels[label]
        else:
            new_label = self.connection.labels.add(label)
            self.commit()  # resolves the correct new label id, before that it's a different transaction id
            self.active_labels[label] = new_label["id"]
            return new_label["id"]

    def get_label_ids(self, labels):
        label_ids = []
        for label in labels:
            if label is None or label == "":
                continue
            label_ids.append(self.get_label_id_or_add_new(label))
        return label_ids

    def add_item_to_project(self, item, project, section=None,
                            labels=None):
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

        label_ids = None
        if labels is not None:
            label_ids = self.get_label_ids(labels)
        new_item = self.connection.add_item(item, project_id=project_id,
                                            labels=label_ids)

        # somehow, the section is not correctly set with the previous command
        # as such, the following is necessary
        if section_id is not None:
            self.connection.items.move(new_item["id"], section_id=section_id)

        self.commit()
        self.sync()

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
                        if (
                                task["due"]["is_recurring"] is True
                                or task["due"]["date"] is not None
                        ):
                            continue
                self.connection.items.delete(task["id"])

        self.commit()
        self.sync()
