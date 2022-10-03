import datetime
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict

import pandas as pd
from omegaconf import DictConfig
from structlog import get_logger
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project, Task

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
    connection: TodoistAPI = field(init=False)
    projects: Dict[str, Project] = field(init=False)

    # used_labels: dict = field(init=False)

    # TODO what is proper way for paths? relative or wih home?
    def __post_init__(self):
        with open(Path(ABS_FILE_PATH, self.config.token_file_path), "r") as f:
            token = f.read().strip()
        self.connection = TodoistAPI(token)
        self.projects = self._get_projects()

    @staticmethod
    def _clean_label(label):
        cleaned = re.sub(r"\s&\s", " and ", label).strip()
        return re.sub(r"[\s_]+", "_", cleaned).strip()

    @staticmethod
    def _get_due_datetime_str(due_datetime: datetime.datetime) -> str:
        return due_datetime.strftime("on %Y-%m-%d at %H:%M")

    def _get_projects(self) -> Dict[str, Project]:
        return {
            project.name.casefold(): project
            for project in self.connection.get_projects()
        }

    def add_defrost_task_to_active_tasks(self):
        raise NotImplementedError("Defrost tasks are not implemented yet!")

    def add_task_to_project(
        self,
        task: str,
        due_date: datetime.datetime = None,
        project: str = None,
        project_id: str = None,
        section: str = None,
        section_id: str = None,
        label_list: list = None,
        description: str = None,
        priority: int = 1,
    ) -> Task:

        due_date_str = None
        if due_date:
            due_date_str = self._get_due_datetime_str(due_date)

        FILE_LOGGER.info(
            "[todoist add]",
            task=task,
            due_date=due_date_str,
            project=project,
            section=section,
            priority=priority,
            labels=label_list,
            description=description,
        )

        if project_id is None and project is not None:
            project_id = self.get_project_id(project)
            if section_id is None and section is not None:
                section_id = self.get_section_id(project_id, section)

        if label_list is None:
            label_list = ["app"]
        else:
            label_list = [self._clean_label(label) for label in label_list]
            label_list += ["app"]

        new_task = self.connection.add_task(
            content=task,
            due_string=due_date_str,
            description=description,
            project_id=project_id,
            section_id=section_id,
            labels=label_list,
            priority=priority,
        )

        # verify that new task found; if not fails
        # TODO if fails often, then add tenacity around add/check
        return self.connection.get_task(task_id=new_task.id)

    def delete_all_items_in_project(
        self,
        project: str,
        no_recurring: bool = True,
        only_app_generated: bool = True,
        only_delete_after_date: date = None,
    ):

        FILE_LOGGER.info(
            "[todoist delete]",
            action="delete items in project",
            project=project,
        )

        project_id = self.get_project_id(project)
        tasks_deleted = 0
        for task in self.connection.get_tasks(project_id=project_id):
            if task.is_completed:
                continue
            if task.due is not None:
                if no_recurring and task.due.is_recurring and task.due.date:
                    continue
                if only_delete_after_date and task.due.date:
                    if (
                        pd.to_datetime(task.due.date).date()
                        <= only_delete_after_date
                    ):
                        continue
            if only_app_generated and "app" not in task.labels:
                continue

            self.connection.delete_task(task_id=task.id)
            tasks_deleted += 1

        FILE_LOGGER.info(
            "[todoist delete]", action=f"Deleted {tasks_deleted} tasks!"
        )

    def get_project_id(self, project_name: str) -> str:
        try:
            return self.projects[project_name.casefold()].id
        except KeyError:
            raise TodoistKeyError(tag="project_id", value=project_name)

    def get_section_id(self, project_id: str, section_name: str) -> str:
        # TODO could we save time by loading all sections
        #  & putting in list with key for project_id?
        for section in self.connection.get_sections(project_id=project_id):
            if section.name.casefold() == section_name.casefold():
                return section.id
        raise TodoistKeyError(tag="section_id", value=section_name)

    # TODO implement defrost task uploader
    def retrieve_freezer(self):
        raise NotImplementedError("Should implement this for defrost!")
        # freezer_contents = defaultdict(list)
        # for task in self.connection.state["items"]:
        #     if task["project_id"] in [self.get_project_id("Freezer")]:
        #         freezer_contents["title"].append(task["content"])
        #         # TODO implement type based on section name
        #         freezer_contents["type"].append("undefined")
        # return pd.DataFrame(freezer_contents)
