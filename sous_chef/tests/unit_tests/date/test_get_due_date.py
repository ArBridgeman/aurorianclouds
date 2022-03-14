import datetime

import pytest
from freezegun import freeze_time
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime

FROZEN_DATE = "2022-01-14"


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
            ("casefold", ["breakfast", "lunch", "dinner"]),
            ("lower", ["breakfast", "lunch", "dinner"]),
            ("capitalize", ["Breakfast", "Lunch", "Dinner"]),
            ("upper", ["BREAKFAST", "LUNCH", "DINNER"]),
        ],
    )
    def test_name_list(string_method, expected_list):
        assert MealTime.name_list(string_method) == expected_list


class TestDueDatetimeFormatter:
    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test_get_anchor_date():
        # TODO update when anchor date made configurable
        anchor_date = DueDatetimeFormatter().get_anchor_date()
        assert anchor_date == datetime.date(year=2022, month=1, day=14)
        assert anchor_date.weekday() == 4

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test_get_calendar_week():
        assert DueDatetimeFormatter().get_calendar_week() == 2

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test_get_due_datetime_with_meal_time():
        assert DueDatetimeFormatter().get_due_datetime_with_meal_time(
            "monday", "dinner"
        ) == create_datetime(day=17, hour=18, minute=15)

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test_get_due_datetime_with_hour_minute():
        assert DueDatetimeFormatter().get_due_datetime_with_hour_minute(
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
    def test__get_anchor_date_at_midnight(weekday, day):
        assert DueDatetimeFormatter()._get_anchor_date_at_midnight(
            weekday
        ) == create_datetime(day)

    @staticmethod
    @freeze_time(FROZEN_DATE)
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
    def test__get_date_relative_to_anchor(weekday, day):
        assert DueDatetimeFormatter()._get_date_relative_to_anchor(
            weekday
        ) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize(
        "meal_time,hour,minute",
        [("breakfast", 8, 30), ("lunch", 11, 30), ("dinner", 18, 15)],
    )
    def test__get_meal_time_hour_minute(meal_time, hour, minute):
        assert DueDatetimeFormatter()._get_meal_time_hour_minute(meal_time) == (
            hour,
            minute,
        )

    @staticmethod
    @pytest.mark.parametrize("meal_time", ["Dinner", "diNNeR", "DINNER"])
    def test__get_meal_time_hour_minute_alternate_capitalization(meal_time):
        assert DueDatetimeFormatter()._get_meal_time_hour_minute(meal_time) == (
            18,
            15,
        )

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
    def test__get_weekday_index(weekday, index):
        assert DueDatetimeFormatter()._get_weekday_index(weekday) == index

    @staticmethod
    @pytest.mark.parametrize("weekday", ["Monday", "moNDay", "MONDAY"])
    def test__get_weekday_index_alternate_capitalization(weekday):
        assert DueDatetimeFormatter()._get_weekday_index(weekday) == 0

    @staticmethod
    @pytest.mark.parametrize("hour,minute", [(0, 0), (1, 31), (23, 59)])
    def test__set_specified_time(hour, minute):
        initial_datetime = create_datetime(day=17)
        assert initial_datetime.hour == 0
        assert initial_datetime.minute == 0

        assert DueDatetimeFormatter()._set_specified_time(
            initial_datetime, hour, minute
        ) == create_datetime(day=17, hour=hour, minute=minute)
