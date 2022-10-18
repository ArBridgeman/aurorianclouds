import datetime

import pytest
from freezegun import freeze_time
from sous_chef.date.get_due_date import (
    DueDatetimeFormatter,
    MealTime,
    get_weekday_index,
)
from tests.conftest import FROZEN_DATE


def create_datetime(
    day: int,
    year: int = 2022,
    month: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
):
    return datetime.datetime(
        year=year, month=month, day=day, hour=hour, minute=minute, second=second
    )


class TestExtendedEnum:
    @staticmethod
    @pytest.mark.parametrize(
        "string_method,expected_list",
        [
            ("casefold", ["breakfast", "lunch", "snack", "dinner"]),
            ("lower", ["breakfast", "lunch", "snack", "dinner"]),
            ("capitalize", ["Breakfast", "Lunch", "Snack", "Dinner"]),
            ("upper", ["BREAKFAST", "LUNCH", "SNACK", "DINNER"]),
        ],
    )
    def test_name_list(string_method, expected_list):
        assert MealTime.name_list(string_method) == expected_list


class TestWeekdayIndex:
    @staticmethod
    @pytest.mark.parametrize(
        "weekday,index",
        [
            ("monday", 0),
            ("tuesday", 1),
            ("wednesday", 2),
            ("thursday", 3),
            ("friday", 4),
            ("saturday", 5),
            ("sunday", 6),
        ],
    )
    def test_check_index(frozen_due_datetime_formatter, weekday, index):
        assert get_weekday_index(weekday) == index

    @staticmethod
    @pytest.mark.parametrize("weekday", ["Monday", "moNDay", "MONDAY"])
    def test_alternate_capitalization(weekday):
        assert get_weekday_index(weekday) == 0


class TestDueDatetimeFormatter:
    @staticmethod
    @freeze_time("2022-01-10")
    @pytest.mark.parametrize(
        "anchor_day,expected_day,expected_index",
        [
            ("Monday", 10, 0),
            ("Tuesday", 11, 1),
            ("Wednesday", 12, 2),
            ("Thursday", 13, 3),
            ("Friday", 14, 4),
            ("Saturday", 15, 5),
            ("Sunday", 16, 6),
        ],
    )
    def test_get_anchor_date(anchor_day, expected_day, expected_index):
        anchor_date = DueDatetimeFormatter(
            anchor_day=anchor_day
        ).get_anchor_date()
        assert anchor_date == datetime.date(
            year=2022, month=1, day=expected_day
        )
        assert anchor_date.weekday() == expected_index

    @staticmethod
    def test_get_calendar_week(frozen_due_datetime_formatter):
        assert frozen_due_datetime_formatter.get_calendar_week() == 2

    @staticmethod
    def test_get_due_datetime_with_meal_time(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_meal_time(
            "monday", "dinner"
        ) == create_datetime(day=17, hour=18, minute=15)

    @staticmethod
    def test_get_due_datetime_with_hour_minute(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_time(
            "monday", hour=14, minute=15
        ) == create_datetime(day=17, hour=14, minute=15)

    @staticmethod
    @freeze_time(FROZEN_DATE)
    @pytest.mark.parametrize(
        "weekday,day",
        [
            ("friday", 14),
            ("saturday", 15),
            ("sunday", 16),
            ("monday", 14),
            ("tuesday", 14),
            ("wednesday", 14),
            ("thursday", 14),
        ],
    )
    def test__get_anchor_date_at_midnight(
        frozen_due_datetime_formatter, weekday, day
    ):
        assert frozen_due_datetime_formatter._get_anchor_date_at_midnight(
            weekday
        ) == create_datetime(day)

    @staticmethod
    @freeze_time("2022-01-10")
    @pytest.mark.parametrize(
        "weekday,day",
        [
            ("wednesday", 12),
            ("thursday", 13),
            ("friday", 14),
            ("saturday", 15),
            ("sunday", 16),
            ("monday", 17),
            ("tuesday", 18),
        ],
    )
    def test_get_date_relative_to_anchor_tuesday(
        frozen_due_datetime_formatter, weekday, day
    ):
        assert DueDatetimeFormatter(
            anchor_day="Tuesday"
        ).get_date_relative_to_anchor(weekday) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize(
        "weekday,day",
        [
            ("saturday", 15),
            ("sunday", 16),
            ("monday", 17),
            ("tuesday", 18),
            ("wednesday", 19),
            ("thursday", 20),
            ("friday", 21),
        ],
    )
    def test_get_date_relative_to_anchor_friday(
        frozen_due_datetime_formatter, weekday, day
    ):
        assert frozen_due_datetime_formatter.get_date_relative_to_anchor(
            weekday
        ) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize(
        "meal_time,hour,minute",
        [("breakfast", 8, 30), ("lunch", 11, 30), ("dinner", 18, 15)],
    )
    def test__get_meal_time_hour_minute(
        frozen_due_datetime_formatter, meal_time, hour, minute
    ):
        assert frozen_due_datetime_formatter._get_meal_time_hour_minute(
            meal_time
        ) == (
            hour,
            minute,
        )

    @staticmethod
    @pytest.mark.parametrize("meal_time", ["Dinner", "diNNeR", "DINNER"])
    def test__get_meal_time_hour_minute_alternate_capitalization(
        frozen_due_datetime_formatter, meal_time
    ):
        assert frozen_due_datetime_formatter._get_meal_time_hour_minute(
            meal_time
        ) == (
            18,
            15,
        )

    @staticmethod
    @pytest.mark.parametrize("hour,minute", [(0, 0), (1, 31), (23, 59)])
    def test__set_specified_time(frozen_due_datetime_formatter, hour, minute):
        initial_datetime = create_datetime(day=17)
        assert initial_datetime.hour == 0
        assert initial_datetime.minute == 0

        assert frozen_due_datetime_formatter._set_specified_time(
            initial_datetime, hour, minute
        ) == create_datetime(day=17, hour=hour, minute=minute)
