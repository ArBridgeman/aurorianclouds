from datetime import datetime

import pytest


class TestTodoistHelper:
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
    def test__clean_label(todoist_helper, label, cleaned_label):
        assert todoist_helper._clean_label(label) == cleaned_label

    @staticmethod
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
    def test__get_due_date_str(todoist_helper, due_date, string):
        assert todoist_helper._get_due_datetime_str(due_date) == string

    @staticmethod
    @pytest.mark.parametrize(
        "due_date",
        [None, 42, "2022-02-22"],
    )
    def test__get_due_date_str_raise_attribute_error(todoist_helper, due_date):
        with pytest.raises(AttributeError):
            todoist_helper._get_due_datetime_str(due_date)
