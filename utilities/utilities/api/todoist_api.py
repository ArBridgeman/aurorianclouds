import logging
from pathlib import Path
from typing import Dict

import tenacity
from structlog import get_logger
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project

from utilities.api.base_classes.todoist import (
    AbstractTodoistHelper,
    TodoistKeyError,
)

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


class TodoistHelper(AbstractTodoistHelper):
    def __post_init__(self):
        with open(Path(ABS_FILE_PATH, self.config.token_file_path), "r") as f:
            token = f.read().strip()
        self.connection = TodoistAPI(token)
        self.projects = self._get_projects()

    def _get_projects(self) -> Dict[str, Project]:
        return {
            project.name.casefold(): project
            for project in self.connection.get_projects()
        }

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=20),
        after=tenacity.after_log(FILE_LOGGER, logging.DEBUG),
    )
    def _add_task(self, **kwargs):
        return self.connection.add_task(**kwargs)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=20),
        after=tenacity.after_log(FILE_LOGGER, logging.DEBUG),
    )
    def _get_task(self, task_id):
        return self.connection.get_task(task_id=task_id)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(5),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=20),
        after=tenacity.after_log(FILE_LOGGER, logging.DEBUG),
    )
    def _delete_task(self, task_id):
        return self.connection.delete_task(task_id=task_id)

    def get_section_id(self, project_id: str, section_name: str) -> str:
        # TODO could we save time by loading all sections
        #  & putting in list with key for project_id?
        for section in self.connection.get_sections(project_id=project_id):
            if section.name.casefold() == section_name.casefold():
                return section.id
        raise TodoistKeyError(tag="section_id", value=section_name)
