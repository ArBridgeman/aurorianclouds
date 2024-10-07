from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from todoist_api_python.models import Project, Section, Task

from utilities.api.todoist_api import TodoistHelper

DEFAULT_SECTION = "section"


class LocalTodoistConnection:
    tasks: List[Task] = []
    projects: List[Project] = []
    sections: list[Section] = []

    def get_task(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task

    def get_tasks(self, project_id: str) -> List[Task]:
        return [task for task in self.tasks if task.project_id == project_id]

    def get_projects(self) -> List[Project]:
        return self.projects

    def get_sections(self, project_id: str) -> List[Section]:
        return [
            section
            for section in self.sections
            if section.project_id == project_id
        ]

    def add_project(
        self, project_name: str, project_id: Optional[str] = None
    ) -> str:
        if project_id is None:
            project_id = str(uuid4())
        project = Project(
            name=project_name,
            color="teal",
            comment_count=0,
            id=project_id,
            is_favorite=False,
            is_inbox_project=False,
            is_shared=True,
            is_team_inbox=False,
            order=1,
            parent_id=None,
            url="https://not-real",
            view_style="list",
            can_assign_tasks=False,
        )
        self.projects.append(project)
        return project.id

    def add_section(self, project_id: str, section_name: str):
        section = Section(
            name=section_name, id=str(uuid4()), order=1, project_id=project_id
        )
        self.sections.append(section)

    @staticmethod
    def get_due(due_string: str) -> Dict:
        is_recurring = False
        date = due_string
        if "every" in due_string:
            is_recurring = True
            date = str(datetime.today())

        return {
            "date": date,
            "is_recurring": is_recurring,
            "string": due_string,
            "datetime": date,
            "timezone": "UTC",
        }

    def add_task(
        self, project_id: str, section_id: Optional[str] = None, **kwargs
    ):
        default_task_kwargs = dict(
            content="",
            added_at=datetime.now().strftime("%Y-%m-%d %H:%M:%s"),
            added_by_uid=str(uuid4()),
            description=None,
            id=str(uuid4()),
            labels=[],
            child_order=0,
            priority=1,
            project_id=project_id,
            parent_id=0,
            section_id=section_id,
            sync_id=str(uuid4()),
        )
        task_values = default_task_kwargs | {**kwargs}
        task_values["content"] = task_values["content"].strip()
        if task_values["description"] is None:
            task_values["description"] = ""
        task_values["labels"] = sorted(task_values["labels"])

        if task_values.get("due_string") is not None:
            due_string = task_values["due_string"]
            task_values["due"] = self.get_due(due_string)

        task = Task.from_quick_add_response(task_values)
        self.tasks.append(task)
        return task

    def delete_task(self, task_id: str):
        self.tasks = [task for task in self.tasks if task.id != task_id]


class DebugTodoistHelper(TodoistHelper):
    connection: LocalTodoistConnection

    def __post_init__(self):
        pass

    def set_connection(self, connection: LocalTodoistConnection):
        self.connection = connection
        self.projects = self._get_projects()
