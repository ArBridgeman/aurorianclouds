from datetime import date, datetime
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest
from tests.conftest import DEFAULT_PROJECT, DEFAULT_SECTION

from utilities.api.base_classes.todoist import (
    TodoistDeletionRejectedError,
    TodoistKeyError,
    get_due_datetime_str,
)
from utilities.validate_choice import YesNoChoices


class TestTodoistHelper:
    @staticmethod
    @pytest.fixture
    def implementation(debug_todoist_helper, default_project):
        # clean up before test
        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            debug_todoist_helper.delete_all_items_in_project(
                project=default_project, skip_recurring=False
            )
        # used to determine which fixture is being used
        yield debug_todoist_helper

    @staticmethod
    @pytest.fixture
    def pytest_area_project_id(local_todoist_project_id):
        # used to determine which fixture is being used
        return local_todoist_project_id

    @staticmethod
    def _get_task_count(todoist_helper, project_id):
        return len(todoist_helper.connection.get_tasks(project_id=project_id))

    @staticmethod
    def _log_add_task(
        task: str,
        due_string: Optional[str] = None,
        due_date: Optional[datetime] = None,
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
            "due_string": due_string,
            "due_date": due_date,
            "project": DEFAULT_PROJECT,
            "section": section,
            "priority": priority,
            "labels": label_list,
            "description": description,
            "parent_id": parent_id,
        }

    @staticmethod
    def test__post_init__(implementation):
        assert isinstance(implementation.projects, Dict)
        assert {"menu", "groceries", DEFAULT_PROJECT.lower()} <= set(
            implementation.projects.keys()
        )

    @pytest.mark.parametrize(
        "key,value",
        [
            pytest.param(None, None, id="no-kwargs"),
            pytest.param(
                "description", "non-null description", id="with-description"
            ),
            pytest.param("label_list", ["dummy_label"], id="with-label"),
            pytest.param("priority", 4, id="with-priority"),
            pytest.param(
                "due_date",
                datetime(year=2050, month=1, day=1),
                id="with-due-date",
            ),
            pytest.param("section", "Test-section", id="with-section"),
        ],
    )
    def test_add_task_to_project(
        self, implementation, pytest_area_project_id, log, key, value
    ):
        # set up
        task_kwarg = {"task": f"add task with {key}"}
        if key:
            task_kwarg[key] = value

        # execute
        task = implementation.add_task_to_project(
            **task_kwarg,
            project=DEFAULT_PROJECT,
        )

        # checks
        assert task.id == task.id
        assert task.is_completed is False
        assert task.content == task_kwarg["task"].strip()
        assert task.description == task_kwarg.get("description", "")
        assert task.project_id == pytest_area_project_id
        assert task.labels == ["app"] + task_kwarg.get("label_list", [])
        assert task.priority == task_kwarg.get("priority", 1)

        if key == "due_date":
            task_kwarg["due_string"] = get_due_datetime_str(
                task_kwarg["due_date"]
            )
            assert task.due.string == task_kwarg["due_string"]
        else:
            assert task.due is None

        section_id = None
        if task_kwarg.get("section"):
            section_id = implementation.get_section_id(
                project_id=task.project_id, section_name=task_kwarg["section"]
            )
        assert task.section_id == section_id

        assert log.events == [self._log_add_task(**task_kwarg)]

    def test_delete_all_items_in_project_user_rejects_deletion_raises_error(
        self, implementation, pytest_area_project_id
    ):
        implementation.connection.add_task(
            content="after_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-03",
        )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

        with pytest.raises(TodoistDeletionRejectedError):
            with patch("builtins.input", side_effect=[YesNoChoices.no.value]):
                implementation.delete_all_items_in_project(
                    project=DEFAULT_PROJECT,
                    only_delete_after_date=date(year=2021, month=4, day=2),
                )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

    def test_delete_all_items_in_project_skip_recurring(
        self, implementation, pytest_area_project_id
    ):
        implementation.connection.add_task(
            content="recurring_task",
            project_id=pytest_area_project_id,
            due_string="every Monday",
        )

        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            implementation.delete_all_items_in_project(
                project=DEFAULT_PROJECT, skip_recurring=True
            )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            implementation.delete_all_items_in_project(
                project=DEFAULT_PROJECT, skip_recurring=False
            )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 0
        )

    def test_delete_all_items_in_project_only_delete_after_date(
        self, implementation, pytest_area_project_id
    ):
        implementation.connection.add_task(
            content="before_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-01",
        )
        implementation.connection.add_task(
            content="on_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-02",
        )
        implementation.connection.add_task(
            content="after_delete_date",
            project_id=pytest_area_project_id,
            due_string="2021-04-03",
        )
        implementation.connection.add_task(
            content="no due date",
            project_id=pytest_area_project_id,
        )

        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 4
        )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            implementation.delete_all_items_in_project(
                project=DEFAULT_PROJECT,
                only_delete_after_date=date(year=2021, month=4, day=2),
            )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 3
        )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            implementation.delete_all_items_in_project(
                project=DEFAULT_PROJECT,
                only_delete_after_date=date(year=2021, month=3, day=28),
            )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

    def test_delete_all_items_in_project_only_with_label(
        self, implementation, pytest_area_project_id
    ):
        implementation.connection.add_task(
            content="has_relevant_label",
            project_id=pytest_area_project_id,
            labels=["relevant-label"],
        )
        implementation.connection.add_task(
            content="not_relevant_label",
            project_id=pytest_area_project_id,
            labels=["not-relevant-label"],
        )

        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 2
        )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            implementation.delete_all_items_in_project(
                project=DEFAULT_PROJECT, only_with_label="relevant-label"
            )
        assert (
            self._get_task_count(
                todoist_helper=implementation, project_id=pytest_area_project_id
            )
            == 1
        )

    @staticmethod
    @pytest.mark.parametrize(
        "project_name",
        ["Menu", "Groceries", DEFAULT_PROJECT],
    )
    def test_get_project_id_if_exists(implementation, project_name):
        assert implementation.get_project_id(project_name) is not None

    @staticmethod
    def test_get_section_id_if_exists(implementation):
        project_id = implementation.get_project_id(DEFAULT_PROJECT)
        assert (
            implementation.get_section_id(
                project_id=project_id, section_name=DEFAULT_SECTION
            )
            is not None
        )

    @staticmethod
    def test_get_section_id_if_not_exists(implementation):
        with pytest.raises(TodoistKeyError) as error:
            implementation.get_section_id("2228326717", "not-a-section-name")
        assert str(error.value) == (
            "[todoist key error]: tag=section_id for "
            "value=not-a-section-name"
        )


@pytest.mark.todoist
class TestTodoistHelperWithApi(TestTodoistHelper):
    @staticmethod
    @pytest.fixture
    def implementation(todoist_helper_with_api, default_project):
        # clean up before running test
        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            todoist_helper_with_api.delete_all_items_in_project(
                project=default_project, skip_recurring=False
            )
        # used to determine which fixture is being used
        yield todoist_helper_with_api

    @staticmethod
    @pytest.fixture
    def pytest_area_project_id(todoist_helper_with_api):
        return todoist_helper_with_api.get_project_id(DEFAULT_PROJECT)
