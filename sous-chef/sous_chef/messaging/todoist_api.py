import datetime
import itertools
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

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class TodoistKeyError(Exception):
    tag: str
    value: str
    message: str = "[todoist key error]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}: tag={self.tag} for value={self.value}"


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
        self.active_labels = self._get_active_labels()

    def sync(self):
        self.connection.sync()

    def commit(self):
        self.connection.commit()

    # TODO implement defrost task uploader
    def add_defrost_task_to_active_tasks(self):
        NotImplementedError("Defrost tasks are not implemented yet!")

    def retrieve_freezer(self):
        freezer_contents = defaultdict(list)
        for task in self.connection.state["items"]:
            if task["project_id"] in [self._get_project_id("Freezer")]:
                freezer_contents["title"].append(task["content"])
                # TODO implement type based on section name
                freezer_contents["type"].append("undefined")
        return pd.DataFrame(freezer_contents)

    def get_label_id_or_add_new(self, label):
        label = self._clean_label(label)
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

    def add_task_list_to_project_with_due_date_list(
        self,
        task_list: list[str],
        project: str = None,
        section: str = None,
        due_date_list: list[datetime.datetime] = None,
        priority: int = 1,
    ):

        project_id = None
        if project is not None:
            project_id = self._get_project_id(project)

        section_id = None
        if section is not None:
            section_id = self._get_section_id(section)

        for (task, due_date) in zip(task_list, due_date_list):
            self.add_task_to_project(
                task=task,
                due_date=due_date,
                project=project,
                project_id=project_id,
                section=section,
                section_id=section_id,
                priority=priority,
            )

    def add_task_list_to_project_with_label_list(
        self,
        task_list: list[str],
        project: str = None,
        section: str = None,
        label_list: list[tuple] = None,
        priority: int = 1,
    ):
        project_id = None
        if project is not None:
            project_id = self._get_project_id(project)

        section_id = None
        if section is not None:
            section_id = self._get_section_id(section)

        for (task, labels) in zip(task_list, label_list):
            self.add_task_to_project(
                task=task,
                label_list=list(itertools.chain(*labels)),
                project=project,
                project_id=project_id,
                section=section,
                priority=priority,
                section_id=section_id,
            )

    def add_task_to_project(
        self,
        task: str,
        due_date: datetime.datetime = None,
        project: str = None,
        project_id: int = None,
        section: str = None,
        section_id: int = None,
        label_list: list = None,
        priority: int = 1,
    ):

        due_date_str = None
        if due_date:
            due_date_str = self._get_due_date_str(due_date)

        FILE_LOGGER.info(
            "[todoist add]",
            task=task,
            due_date=due_date_str,
            project=project,
            section=section,
            priority=priority,
            labels=label_list,
        )

        if project_id is None and project is not None:
            project_id = self._get_project_id(project)

        if section_id is None and section is not None:
            section_id = self._get_section_id(section)

        # TODO consolidate label_list and label_ids into 1-2 methods
        # TODO have functions handle None cases below instead of here
        # (e.g. _get_due_date_str)
        if label_list is None:
            label_list = ["app"]
        label_list += ["app"]

        label_ids = None
        if label_list is not None:
            label_ids = self.get_label_ids(label_list)

        new_item = self.connection.add_item(
            task,
            date_string=due_date_str,
            project_id=project_id,
            labels=label_ids,
            priority=priority,
        )
        self.commit()

        # sometimes due to Todoist api, new_item gets lost/changed in process
        if "id" not in new_item:
            new_item = self.get_item_in_project(project, task)

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
        project_id = self._get_project_id(project)

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
        :param sleep_in_seconds: int (optional)
        Adds wait time in specified seconds before syncing
        """
        FILE_LOGGER.info(
            "[todoist delete]",
            action="delete items in project",
            project=project,
        )

        project_id = self._get_project_id(project)
        sleep(sleep_in_seconds)
        self.sync()

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
            self.connection.items.delete(to_delete)
            self.commit()

        self.sync()

    @staticmethod
    def _clean_label(label):
        cleaned = re.sub(r"\s&\s", " and ", label).strip()
        return re.sub(r"[\s\_]+", "_", cleaned).strip()

    def _get_active_labels(self):
        label_dict = {}
        for label in self.connection.labels.state["labels"]:
            label_dict[label["name"]] = label["id"]
        return label_dict

    @staticmethod
    def _get_due_date_str(due_date: datetime.datetime) -> str:
        return due_date.strftime("on %Y-%m-%d at %H:%M")

    def _get_project_id(self, desired_project):
        for project in self.connection.state["projects"]:
            if desired_project == project.data.get("name"):
                return project.data.get("id")
        raise TodoistKeyError(tag="project_id", value=desired_project)

    def _get_section_id(self, desired_section):
        for project in self.connection.state["sections"]:
            if desired_section == project.data.get("name"):
                return project.data.get("id")
        raise TodoistKeyError(tag="section_id", value=desired_section)
