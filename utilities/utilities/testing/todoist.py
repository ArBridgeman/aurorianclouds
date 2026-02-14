from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from todoist_api_python.models import Due, Project, Section, Task

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
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if project_id is None:
            project_id = str(uuid4())
        project = Project(
            id=project_id,
            name=project_name,
            description="local_project",
            order=1,
            color="teal",
            is_collapsed=False,
            is_shared=True,
            is_favorite=False,
            is_archived=False,
            is_inbox_project=False,
            parent_id=None,
            view_style="list",
            can_assign_tasks=False,
            created_at=now_iso,
            updated_at=now_iso,
        )
        self.projects.append(project)
        return project.id

    def add_section(self, project_id: str, section_name: str):
        section = Section(
            id=str(uuid4()),
            name=section_name,
            project_id=project_id,
            is_collapsed=False,
            order=1,
        )
        self.sections.append(section)

    @staticmethod
    def get_due(due_string: str) -> Due:
        is_recurring = False
        date = due_string
        if "every" in due_string:
            is_recurring = True
            date = str(datetime.today())

        return Due(
            date=date,
            string=due_string,
            is_recurring=is_recurring,
            timezone="UTC",
        )

    def add_task(
        self, project_id: str, section_id: Optional[str] = None, **kwargs
    ):
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%s")
        default_task_kwargs = dict(
            id=str(uuid4()),
            content="",
            description=None,
            project_id=project_id,
            section_id=section_id,
            parent_id=0,
            labels=[],
            priority=1,
            due=None,
            deadline=None,
            duration=None,
            is_collapsed=False,
            order=0,
            assignee_id=None,
            assigner_id=None,
            completed_at=None,
            created_at=time_now,
            updated_at=time_now,
            creator_id=str(uuid4()),
        )
        task_values = default_task_kwargs | {**kwargs}
        task_values["content"] = task_values["content"].strip()
        if task_values["description"] is None:
            task_values["description"] = ""
        task_values["labels"] = sorted(task_values["labels"])

        if task_values.get("due_string") is not None:
            due_string = task_values.pop("due_string")
            task_values["due"] = self.get_due(due_string)

        print(task_values.keys())
        task = Task(**task_values)
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
