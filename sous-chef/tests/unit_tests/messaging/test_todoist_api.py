from datetime import datetime
from unittest.mock import patch

import pytest
from hydra import compose, initialize
from sous_chef.messaging.todoist_api import TodoistHelper


@pytest.fixture
def mock_todoist_helper():
    with initialize(version_base=None, config_path="../../../config/messaging"):
        config = compose(config_name="todoist_api")
        with patch.object(TodoistHelper, "__post_init__", lambda x: None):
            return TodoistHelper(config)


class TestTodoistHelper:
    @staticmethod
    @pytest.mark.parametrize(
        "label,cleaned_label",
        [
            ("french onion soup", "french_onion_soup"),
            ("pb and jelly", "pb_and_jelly"),
            ("cali _ burgers", "cali_burgers"),
        ],
    )
    def test__clean_label(mock_todoist_helper, label, cleaned_label):
        assert mock_todoist_helper._clean_label(label) == cleaned_label

    @staticmethod
    @pytest.mark.parametrize(
        "due_date,string",
        [
            (
                datetime(year=2022, month=1, day=1, hour=12, minute=4),
                "on 2022-01-01 at 12:04",
            ),
        ],
    )
    def test__get_due_date_str(mock_todoist_helper, due_date, string):
        assert mock_todoist_helper._get_due_datetime_str(due_date) == string

    @staticmethod
    @pytest.mark.parametrize(
        "due_date",
        [(None), (42), ("2022-02-22")],
    )
    def test__get_due_date_str_raise_attribute_error(
        mock_todoist_helper, due_date
    ):
        with pytest.raises(AttributeError):
            mock_todoist_helper._get_due_datetime_str(due_date)
