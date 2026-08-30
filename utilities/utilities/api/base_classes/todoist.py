import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Union

import pandas as pd
from omegaconf import DictConfig
from structlog import get_logger
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project, Section, Task

from utilities.validate_choice import YesNoChoices

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
class TodoistDeletionRejectedError(Exception):
    number_tasks_to_be_deleted: int
    message: str = "[todoist deletion rejected error]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message}: user rejected to delete "
            f"number_tasks_to_be_deleted={self.number_tasks_to_be_deleted}"
        )


def get_due_datetime_str(due_datetime: datetime) -> str:
    return due_datetime.strftime("on %Y-%m-%d at %H:%M")


@dataclass
class AbstractTodoistHelper(ABC):
    config: DictConfig
    connection: TodoistAPI = field(init=False)
    projects: Dict[str, Project] = field(init=False)

    @abstractmethod
    def __post_init__(self):
        raise NotImplementedError

    @staticmethod
    def _clean_label(label: str) -> str:
        cleaned = re.sub(r"\s&\s", " and ", label).strip()
        return re.sub(r"[\s_]+", "_", cleaned).strip()

    @staticmethod
    def _get_due_date_str(due_date: date) -> str:
        return due_date.strftime("on %Y-%m-%d")

    @abstractmethod
    def _get_projects(self) -> Dict[str, Project]:
        raise NotImplementedError

    def add_task_to_project(
        self,
        task: str,
        due_string: str = None,
        due_date: Union[date, datetime] = None,
        project: str = None,
        project_id: str = None,
        section: str = None,
        section_id: str = None,
        label_list: list[str] = None,
        description: str = None,
        parent_id: str = None,
        priority: int = 1,
    ) -> Task:
        due_date_str = due_string
        if isinstance(due_date, datetime):
            due_date_str = get_due_datetime_str(due_date)
        elif isinstance(due_date, date):
            due_date_str = self._get_due_date_str(due_date)

        FILE_LOGGER.info(
            "[todoist add]",
            task=task,
            due_string=due_date_str,
            due_date=due_date,
            project=project,
            section=section,
            priority=priority,
            labels=label_list,
            description=description,
            parent_id=parent_id,
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

        new_task = self._add_task(
            content=task,
            due_string=due_date_str,
            description=description,
            project_id=project_id,
            section_id=section_id,
            labels=label_list,
            priority=priority,
            parent_id=parent_id,
        )

        return self._get_task(task_id=new_task.id)

    @abstractmethod
    def _add_task(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def _get_task(self, task_id: str) -> Task:
        raise NotImplementedError

    @abstractmethod
    def _delete_task(self, task_id: str):
        raise NotImplementedError

    @abstractmethod
    def _get_tasks(self, project_id: str) -> List[Task]:
        raise NotImplementedError

    def delete_all_items_in_project(
        self,
        project: str,
        skip_recurring: bool = True,
        only_delete_after_date: date = None,
        only_with_label: str = None,
    ) -> int:
        # TODO look into using the API query to reduce subsequent loops
        # manually filtering tasks to decide what gets deleted or not
        project_id = self.get_project_id(project)
        tasks_to_be_deleted = self._get_tasks_to_be_deleted(
            project_id=project_id,
            skip_recurring=skip_recurring,
            only_delete_after_date=only_delete_after_date,
            only_with_label=only_with_label,
        )

        # checking if deletion desired & performing it
        number_tasks_to_be_deleted = len(tasks_to_be_deleted)
        FILE_LOGGER.info(
            "[todoist delete]",
            action="Delete items in project",
            project=project,
            number_tasks_to_be_deleted=number_tasks_to_be_deleted,
        )
        if number_tasks_to_be_deleted > 0:
            choice = YesNoChoices.ask_yes_no(
                f"... delete {number_tasks_to_be_deleted} tasks?"
            )
            if choice == YesNoChoices.no:
                raise TodoistDeletionRejectedError(
                    number_tasks_to_be_deleted=number_tasks_to_be_deleted
                )

            for task in tasks_to_be_deleted:
                self._delete_task(task_id=task.id)
            FILE_LOGGER.info("[todoist delete]", action="Deleted tasks!")

        return number_tasks_to_be_deleted

    def _get_tasks_to_be_deleted(
        self,
        project_id: str,
        skip_recurring: bool,
        only_delete_after_date: date,
        only_with_label: str,
    ) -> List[Task]:
        return [
            task
            for task in self._get_tasks(project_id)
            if self._is_task_eligible_for_deletion(
                task=task,
                skip_recurring=skip_recurring,
                only_delete_after_date=only_delete_after_date,
                only_with_label=only_with_label,
            )
        ]

    def _is_task_eligible_for_deletion(
        self,
        task: Task,
        skip_recurring: bool,
        only_delete_after_date: date,
        only_with_label: str,
    ) -> bool:
        return all(
            (
                self._is_incomplete_task(task),
                self._has_required_due_date(task, only_delete_after_date),
                self._is_not_skipped_recurring_task(task, skip_recurring),
                self._is_after_date(task, only_delete_after_date),
                self._has_required_label(task, only_with_label),
            )
        )

    @staticmethod
    def _is_incomplete_task(task: Task) -> bool:
        return not task.is_completed

    @staticmethod
    def _has_required_due_date(
        task: Task, only_delete_after_date: date
    ) -> bool:
        return not only_delete_after_date or task.due is not None

    @staticmethod
    def _is_not_skipped_recurring_task(
        task: Task, skip_recurring: bool
    ) -> bool:
        return not (
            skip_recurring
            and task.due is not None
            and task.due.is_recurring
            and task.due.date
        )

    @staticmethod
    def _is_after_date(task: Task, only_delete_after_date: date) -> bool:
        if not only_delete_after_date or task.due is None or not task.due.date:
            return True
        return pd.to_datetime(task.due.date).date() > only_delete_after_date

    @staticmethod
    def _has_required_label(task: Task, only_with_label: str) -> bool:
        return not only_with_label or only_with_label in task.labels

    def get_project_id(self, project_name: str) -> str:
        project_name = project_name.casefold()
        project = self.projects.get(project_name)
        if project is None:
            raise TodoistKeyError(tag="project_id", value=project_name)
        return project.id

    @abstractmethod
    def _get_sections(self, project_id: str) -> Dict[str, Section]:
        raise NotImplementedError

    def get_section_id(self, project_id: str, section_name: str) -> str:
        # TODO could we save time by loading all sections
        #  & putting in list with key for project_id?
        sections = self._get_sections(project_id=project_id)
        section_name = section_name.casefold()
        if section_name in sections.keys():
            return sections[section_name].id
        raise TodoistKeyError(tag="section_id", value=section_name)
