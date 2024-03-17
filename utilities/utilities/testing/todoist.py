from typing import Dict

from todoist_api_python.models import Project

from utilities.api.base_classes.todoist import AbstractTodoistHelper


class TestTodoistHelper(AbstractTodoistHelper):
    def __post_init__(self):
        pass

    #     with open(Path(ABS_FILE_PATH, self.config.token_file_path), "r") as f:
    #         token = f.read().strip()
    #     self.connection = TodoistAPI(token)
    #     self.projects = self._get_projects()
    #
    def _get_projects(self) -> Dict[str, Project]:
        pass

    #     return {
    #         project.name.casefold(): project
    #         for project in self.connection.get_projects()
    #     }
    #

    def _add_task(self, **kwargs):
        pass
        # return self.connection.add_task(**kwargs)

    #

    def _get_task(self, task_id):
        pass

    #     return self.connection.get_task(task_id=task_id)

    def _delete_task(self, task_id):
        pass
        # return self.connection.delete_task(task_id=task_id)

    #
    def get_section_id(self, project_id: str, section_name: str) -> str:
        pass

    #     # TODO could we save time by loading all sections
    #     #  & putting in list with key for project_id?
    #     for section in self.connection.get_sections(project_id=project_id):
    #         if section.name.casefold() == section_name.casefold():
    #             return section.id
    #     raise TodoistKeyError(tag="section_id", value=section_name)
