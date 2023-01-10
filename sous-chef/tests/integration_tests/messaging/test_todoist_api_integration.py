from datetime import date, datetime
from typing import Dict, List, Optional

import pytest
from sous_chef.messaging.todoist_api import TodoistKeyError
from tests.integration_tests.util import clean_up_add_todoist_task
from todoist_api_python.api import TodoistAPI

PROJECT = "Pytest-area"


@pytest.fixture
def pytest_area_project_id(todoist_helper):
    return todoist_helper.get_project_id(PROJECT)


@pytest.mark.todoist
class TestTodoistHelper:
    @staticmethod
    def _get_task_count(todoist_helper, project_id):
        return len(todoist_helper.connection.get_tasks(project_id=project_id))

    @staticmethod
    def _log_add_task(
        task: str,
        due_date_str: Optional[str] = None,
        section: Optional[str] = None,
        priority: int = 1,
        label_list: Optional[List] = None,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
    ):
        return {
            "level": "info",
            "event": "[todoist add]",
            "task": task,
            "due_date": due_date_str,
            "project": PROJECT,
            "section": section,
            "priority": priority,
            "labels": label_list,
            "description": description,
            "parent_id": parent_id,
        }

    @staticmethod
    def test__post_init__(todoist_helper):
        assert isinstance(todoist_helper.connection, TodoistAPI)
        assert isinstance(todoist_helper.projects, Dict)
        assert {"menu", "groceries", PROJECT.lower()} <= set(
            todoist_helper.projects.keys()
        )

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
    def test_add_task_to_project(
        self, todoist_helper, pytest_area_project_id, log, task_kwarg
    ):
        task_kwarg["task"] = "add task with " + "".join(task_kwarg.keys())
        task = todoist_helper.add_task_to_project(
            **task_kwarg,
            project=PROJECT,
        )
        clean_up_add_todoist_task(todoist_helper, task.id)

        assert task.id == task.id
        assert task.is_completed is False
        assert task.content == task_kwarg["task"].strip()
        assert task.description == task_kwarg.get("description", "")
        assert task.project_id == pytest_area_project_id
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

    def test_delete_all_items_in_project_skip_recurring(
        self, todoist_helper, pytest_area_project_id
    ):

        # initial delete
        todoist_helper.delete_all_items_in_project(
            project=PROJECT, skip_recurring=False
        )

        todoist_helper.connection.add_task(
            content="recurring_task",
            project_id=pytest_area_project_id,
            due_string="every Monday",
        )

        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 1
        )

        todoist_helper.delete_all_items_in_project(
            project=PROJECT, skip_recurring=True
        )
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 1
        )

        todoist_helper.delete_all_items_in_project(
            project=PROJECT, skip_recurring=False
        )
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 0
        )

    def test_delete_all_items_in_project_only_delete_after_date(
        self, todoist_helper, pytest_area_project_id
    ):
        # initial delete
        todoist_helper.delete_all_items_in_project(
            project=PROJECT, skip_recurring=False
        )

        todoist_helper.connection.add_task(
            content="before_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-01",
        )
        todoist_helper.connection.add_task(
            content="on_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-02",
        )
        todoist_helper.connection.add_task(
            content="after_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-03",
        )
        todoist_helper.connection.add_task(
            content="no due date",
            project_id=pytest_area_project_id,
        )

        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 4
        )

        todoist_helper.delete_all_items_in_project(
            project=PROJECT,
            only_delete_after_date=date(year=2021, month=4, day=2),
        )
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 3
        )

        todoist_helper.delete_all_items_in_project(
            project=PROJECT,
            only_delete_after_date=date(year=2021, month=3, day=28),
        )
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 1
        )

        todoist_helper.delete_all_items_in_project(project=PROJECT)
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 0
        )

    def test_delete_all_items_in_project_only_with_label(
        self, todoist_helper, pytest_area_project_id
    ):
        # initial delete
        todoist_helper.delete_all_items_in_project(
            project=PROJECT, skip_recurring=False
        )

        todoist_helper.connection.add_task(
            content="has_relevant_label",
            project_id=pytest_area_project_id,
            labels=["relevant-label"],
        )
        todoist_helper.connection.add_task(
            content="not_relevant_label",
            project_id=pytest_area_project_id,
            labels=["not-relevant-label"],
        )

        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 2
        )

        todoist_helper.delete_all_items_in_project(
            project=PROJECT, only_with_label="relevant-label"
        )
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 1
        )

        todoist_helper.delete_all_items_in_project(project=PROJECT)
        assert (
            self._get_task_count(
                todoist_helper=todoist_helper, project_id=pytest_area_project_id
            )
            == 0
        )

    @staticmethod
    @pytest.mark.parametrize(
        "project_name",
        ["Menu", "Groceries", PROJECT],
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
