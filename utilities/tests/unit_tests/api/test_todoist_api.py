from datetime import datetime

import pytest

from utilities.api.base_classes.todoist import (
    TodoistKeyError,
    get_due_datetime_str,
)


@pytest.mark.parametrize(
    "due_date,string",
    [
        (
            datetime(year=2022, month=1, day=1, hour=12, minute=4),
            "on 2022-01-01 at 12:04",
        ),
        (datetime(year=2022, month=1, day=1), "on 2022-01-01 at 00:00"),
        (
            datetime(year=2022, month=1, day=1, hour=9, minute=30),
            "on 2022-01-01 at 09:30",
        ),
    ],
)
def test_get_due_date_str(due_date, string):
    assert get_due_datetime_str(due_date) == string


class TestTodoistHelper:
    @staticmethod
    @pytest.fixture
    def implementation(debug_todoist_helper, default_project):
        # used to determine which fixture is being used
        yield debug_todoist_helper

    @staticmethod
    @pytest.mark.parametrize(
        "label,cleaned_label",
        [
            ("french onion soup", "french_onion_soup"),
            ("pb and jelly", "pb_and_jelly"),
            ("cali _ burgers", "cali_burgers"),
            ("pasta & broccoli", "pasta_and_broccoli"),
            ("pasta broccoli", "pasta_broccoli"),
            ("pasta   broccoli", "pasta_broccoli"),
            ("pasta___broccoli", "pasta_broccoli"),
        ],
    )
    def test__clean_label(implementation, label, cleaned_label):
        assert implementation._clean_label(label) == cleaned_label

    @staticmethod
    @pytest.mark.parametrize(
        "due_date",
        [None, 42, "2022-02-22"],
    )
    def test__get_due_date_str_raise_attribute_error(implementation, due_date):
        with pytest.raises(AttributeError):
            implementation._get_due_datetime_str(due_date)

    @staticmethod
    def test_get_project_id_if_not_exists(implementation):
        implementation.projects = {}
        with pytest.raises(TodoistKeyError) as error:
            implementation.get_project_id("not-a-project-name")
        assert str(error.value) == (
            "[todoist key error]: tag=project_id for "
            "value=not-a-project-name"
        )


class TestMockTodoistHelper(TestTodoistHelper):
    @staticmethod
    @pytest.fixture
    def implementation(mock_todoist_helper, default_project):
        # used to determine which fixture is being used
        yield mock_todoist_helper
