from datetime import date, datetime
from typing import Dict, List, Optional

import pytest
from hydra import compose, initialize
from requests.exceptions import HTTPError
from sous_chef.messaging.todoist_api import TodoistHelper, TodoistKeyError
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../../config/messaging"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)


@pytest.mark.todoist
class TestTodoistHelper:
    @staticmethod
    def _clean_up_add_task(todoist_helper, task_id: str) -> Task:
        # delete task
        todoist_helper.connection.delete_task(task_id=task_id)

        # verify task was deleted
        with pytest.raises(HTTPError) as error:
            todoist_helper.connection.get_task(task_id=task_id)
        assert str(error.value) == (
            "404 Client Error: Not Found for url: "
            f"https://api.todoist.com/rest/v2/tasks/{task_id}"
        )

    @staticmethod
    def _log_add_task(
        task: str,
        due_date_str: Optional[str] = None,
        section: Optional[str] = None,
        priority: int = 1,
        label_list: Optional[List] = None,
        description: Optional[str] = None,
    ):
        return {
            "level": "info",
            "event": "[todoist add]",
            "task": task,
            "due_date": due_date_str,
            "project": "Pytest-area",
            "section": section,
            "priority": priority,
            "labels": label_list,
            "description": description,
        }

    @staticmethod
    def test__post_init__(todoist_helper):
        assert isinstance(todoist_helper.connection, TodoistAPI)
        assert isinstance(todoist_helper.projects, Dict)
        assert {"menu", "groceries", "pytest-area"} <= set(
            todoist_helper.projects.keys()
        )

    @staticmethod
    @pytest.mark.parametrize(
        "label,result",
        [
            ("pasta & broccoli", "pasta_and_broccoli"),
            ("pasta broccoli", "pasta_broccoli"),
            ("pasta   broccoli", "pasta_broccoli"),
            ("pasta___broccoli", "pasta_broccoli"),
        ],
    )
    def test__clean_label(todoist_helper, label, result):
        assert todoist_helper._clean_label(label) == result

    @staticmethod
    @pytest.mark.parametrize(
        "due_datetime,result",
        [
            (datetime(year=2022, month=1, day=1), "on 2022-01-01 at 00:00"),
            (
                datetime(year=2022, month=1, day=1, hour=9, minute=30),
                "on 2022-01-01 at 09:30",
            ),
        ],
    )
    def test__get_due_date_str(todoist_helper, due_datetime, result):
        assert todoist_helper._get_due_datetime_str(due_datetime) == result

    @pytest.mark.parametrize(
        "task_kwarg",
        [
            {},
            {"description": "non-null description"},
            {"label_list": ["dummy_label"]},
            {"priority": 4},
            {"due_date": datetime(year=2050, month=1, day=1)},
            {"section": "Test-section"},
        ],
    )
    def test_add_task_to_project(self, todoist_helper, log, task_kwarg):
        task_kwarg["task"] = "add task with" + "".join(task_kwarg.keys())
        task = todoist_helper.add_task_to_project(
            **task_kwarg,
            project="Pytest-area",
        )
        self._clean_up_add_task(todoist_helper, task.id)

        assert task.id == task.id
        assert task.is_completed is False
        assert task.content == task_kwarg["task"]
        assert task.description == task_kwarg.get("description", "")
        assert task.project_id == todoist_helper.get_project_id("Pytest-area")
        assert task.labels == ["app"] + task_kwarg.get("label_list", [])
        assert task.priority == task_kwarg.get("priority", 1)

        if task_kwarg.get("due_date"):
            task_kwarg["due_date_str"] = todoist_helper._get_due_datetime_str(
                task_kwarg["due_date"]
            )
            task_kwarg.pop("due_date")
            assert task.due.string == task_kwarg["due_date_str"]
        else:
            assert task.due is None

        if task_kwarg.get("section"):
            task_kwarg["section_id"] = todoist_helper.get_section_id(
                project_id=task.project_id, section_name=task_kwarg["section"]
            )
        assert task.section_id == task_kwarg.get("section_id")

        if task_kwarg.get("section_id"):
            task_kwarg.pop("section_id")
        assert log.events == [self._log_add_task(**task_kwarg)]

    @staticmethod
    def test_delete_all_items_in_project(todoist_helper, log):
        project = "Pytest-area"
        project_id = todoist_helper.get_project_id(project)

        initial_delete = todoist_helper.delete_all_items_in_project(
            project=project, no_recurring=False, only_app_generated=False
        )

        todoist_helper.connection.add_task(
            content="app task", project_id=project_id, labels=["app"]
        )
        todoist_helper.connection.add_task(
            content="due date task",
            project_id=project_id,
            due_string="on 2025-01-01",
        )
        task_recurring = todoist_helper.connection.add_task(
            content="recurring_task",
            project_id=project_id,
            due_string="every Monday",
        )

        task_all = todoist_helper.connection.get_tasks(project_id=project_id)
        assert len(task_all) == 3

        todoist_helper.delete_all_items_in_project(project=project)
        task_all = todoist_helper.connection.get_tasks(project_id=project_id)
        assert len(task_all) == 2

        todoist_helper.delete_all_items_in_project(
            project=project,
            only_app_generated=False,
            only_delete_after_date=date(year=2024, month=12, day=31),
        )
        task_all = todoist_helper.connection.get_tasks(project_id=project_id)
        assert task_all[0].id == task_recurring.id

        todoist_helper.delete_all_items_in_project(
            project=project, only_app_generated=False, no_recurring=False
        )
        task_all = todoist_helper.connection.get_tasks(project_id=project_id)
        assert len(task_all) == 0

        assert log.events == [
            {
                "action": "delete items in project",
                "event": "[todoist delete]",
                "level": "info",
                "project": "Pytest-area",
            },
            {
                "action": f"Deleted {initial_delete} tasks!",
                "event": "[todoist delete]",
                "level": "info",
            },
            {
                "action": "delete items in project",
                "event": "[todoist delete]",
                "level": "info",
                "project": "Pytest-area",
            },
            {
                "action": "Deleted 1 tasks!",
                "event": "[todoist delete]",
                "level": "info",
            },
            {
                "action": "delete items in project",
                "event": "[todoist delete]",
                "level": "info",
                "project": "Pytest-area",
            },
            {
                "action": "Deleted 1 tasks!",
                "event": "[todoist delete]",
                "level": "info",
            },
            {
                "action": "delete items in project",
                "event": "[todoist delete]",
                "level": "info",
                "project": "Pytest-area",
            },
            {
                "action": "Deleted 1 tasks!",
                "event": "[todoist delete]",
                "level": "info",
            },
        ]

    @staticmethod
    @pytest.mark.parametrize(
        "project_name",
        [
            "Menu",
            "Groceries",
            "Pytest-area",
        ],
    )
    def test_get_project_id_if_exists(todoist_helper, project_name):
        assert todoist_helper.get_project_id(project_name) is not None

    @staticmethod
    def test_get_project_id_if_not_exists(todoist_helper):
        with pytest.raises(TodoistKeyError) as error:
            todoist_helper.get_project_id("not-a-project-name")
        assert str(error.value) == (
            "[todoist key error]: tag=project_id for "
            "value=not-a-project-name"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "project_name,section_name",
        [
            ("Groceries", "Frozen 3"),
            ("Groceries", "Farmland pride"),
        ],
    )
    def test_get_section_id_if_exists(
        todoist_helper, project_name, section_name
    ):
        project_id = todoist_helper.get_project_id(project_name)
        assert (
            todoist_helper.get_section_id(
                project_id=project_id, section_name=section_name
            )
            is not None
        )

    @staticmethod
    def test_get_section_id_if_not_exists(todoist_helper):
        with pytest.raises(TodoistKeyError) as error:
            todoist_helper.get_section_id("2228326717", "not-a-section-name")
        assert str(error.value) == (
            "[todoist key error]: tag=section_id for "
            "value=not-a-section-name"
        )
