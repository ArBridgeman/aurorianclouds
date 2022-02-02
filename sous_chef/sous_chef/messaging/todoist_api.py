import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from time import sleep
from typing import Any

import pandas as pd
import todoist
from omegaconf import DictConfig
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)
ABS_FILE_PATH = Path(__file__).absolute().parent


@dataclass
class TodoistHelper:
    config: DictConfig
    connection: Any = field(init=False)
    active_labels: dict = field(init=False)

    # TODO what is proper way for paths? relative or wih home?
    # TODO distinguish private methods with leading _
    def __post_init__(self):
        with open(Path(ABS_FILE_PATH, self.config.token_file_path), "r") as f:
            token = f.read().strip()
        self.connection = todoist.TodoistAPI(token)
        self.sync()
        self.active_labels = self.get_active_labels()

    def sync(self):
        self.connection.sync()

    def commit(self):
        self.connection.commit()

    def get_active_labels(self):
        label_dict = {}
        for label in self.connection.labels.state["labels"]:
            label_dict[label["name"]] = label["id"]
        return label_dict

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
        NotImplementedError("Defrost tasks are not implemented yet!")

    def retrieve_freezer(self):
        freezer_contents = defaultdict(list)
        for task in self.connection.state["items"]:
            if task["project_id"] in [self.get_project_id("Freezer")]:
                freezer_contents["title"].append(task["content"])
                # TODO implement type based on section name
                freezer_contents["type"].append("undefined")
        return pd.DataFrame(freezer_contents)

    @staticmethod
    def clean_label(label):
        cleaned = re.sub(r"\s\&\s", " and ", label).strip()
        return re.sub(r"\s+", "_", cleaned).strip()

    def get_label_id_or_add_new(self, label):
        label = self.clean_label(label)
        if label in self.active_labels.keys():
            return self.active_labels[label]
        else:
            new_label = self.connection.labels.add(label)
            # get correct new label id; before, it has different transaction id
            self.commit()
            self.active_labels[label] = new_label["id"]
            return new_label["id"]

    def get_label_ids(self, labels):
        label_ids = []
        for label in labels:
            if label is None or label == "":
                continue
            label_ids.append(self.get_label_id_or_add_new(label))
        return label_ids

    def add_item_to_project(
        self,
        item,
        project,
        section=None,
        labels=None,
        due_date_dict=None,
    ):

        FILE_LOGGER.info(
            "[todoist add]",
            item=item,
            due_date_dict=due_date_dict,
            project=project,
            section=section,
            labels=labels,
        )

        project_id = None
        if project is not None:
            project_id = self.get_project_id(project)
            assert (
                project_id is not None
            ), "Id of project {:s} could not be found!".format(project)
        section_id = None
        if section is not None:
            section_id = self.get_section_id(section)
            assert (
                section_id is not None
            ), "Id of section {:s} could not be found!".format(section)

        if labels is None:
            labels = ["app"]
        labels += ["app"]

        label_ids = None
        if labels is not None:
            label_ids = self.get_label_ids(labels)

        date_string = None
        if due_date_dict is not None:
            date_string = due_date_dict.get("string", None)

        new_item = self.connection.add_item(
            item,
            project_id=project_id,
            labels=label_ids,
            date_string=date_string,
        )
        self.commit()

        # sometimes due to Todoist api, new_item gets lost/changed in process
        if "id" not in new_item:
            new_item = self.get_item_in_project(project, item)

        # somehow, the section is not correctly set with the previous command
        # as such, the following is necessary
        if section_id is not None:
            self.connection.items.move(new_item["id"], section_id=section_id)

        self.commit()
        self.sync()

    def get_item_in_project(self, project, item_content):
        all_in_project = self.get_all_items_in_project(project)
        for one_item in all_in_project:
            if one_item["content"] == item_content:
                return one_item

    # todo: change to generator logic?
    def get_all_items_in_project(self, project):
        items = []
        project_id = self.get_project_id(project)
        assert (
            project_id is not None
        ), "Id of project {:s} could not be found!".format(project)
        for item in self.connection.state["items"]:
            if item["project_id"] == project_id:
                items.append(item)
        return items

    def delete_all_items_in_project(
        self,
        project,
        no_recurring: bool = True,
        only_app_generated: bool = True,
        only_delete_after_date: date = None,
        prior_move: str = "Deleted",
        sleep_in_seconds: int = 1,
    ):
        """
        Deletes items in project "project" that fulfil specified properties.
        :param project: string, name of project.
        :param no_recurring: boolean (default: True).
        If True, do not delete recurring items from list.
        :param only_app_generated: boolean (default: True).
        If True, delete entries with label app, the label
        that is added to all app-generated entries by default.
        :param only_delete_after_date: date (default: None).
        Delete entries with a due date after this date.
        :param prior_move: string (optional).
        If not None, move items to relevant section before deleting them.
        :param sleep_in_seconds: int (optional)
        Adds wait time in specified seconds before syncing
        """
        FILE_LOGGER.info(
            "[todoist delete]",
            action="delete items in project",
            project=project,
        )

        project_id = self.get_project_id(project)
        sleep(sleep_in_seconds)
        self.sync()

        section_id = None
        if prior_move is not None:
            section_id = self.get_section_id(prior_move)
            assert (
                section_id is not None
            ), "Id of section {:s} could not be found!".format(prior_move)

        app_added_label_id = self.get_label_id_or_add_new("app")

        for_deletion = []
        for task in self.connection.state["items"]:
            if task["project_id"] == project_id:
                # check if task is already finished or deleted
                if task["in_history"] == 1 or task["is_deleted"] == 1:
                    continue
                if task["due"] is not None:
                    if no_recurring:
                        if (
                            task["due"]["is_recurring"] is True
                            or task["due"]["date"] is not None
                        ):
                            continue
                    if (
                        only_delete_after_date is not None
                        and task["due"]["date"] is not None
                    ):
                        if (
                            pd.to_datetime(task["due"]["date"]).date()
                            <= only_delete_after_date
                        ):
                            continue
                if (
                    only_app_generated
                    and app_added_label_id not in task["labels"]
                ):
                    continue
                for_deletion.append(task["id"])

        FILE_LOGGER.info(
            "[todoist delete]", action=f"Deleting {len(for_deletion)} tasks!"
        )
        for to_delete in for_deletion:
            if section_id is not None:
                self.connection.items.move(to_delete, section_id=section_id)
            self.connection.items.delete(to_delete)
            self.commit()

        self.sync()
