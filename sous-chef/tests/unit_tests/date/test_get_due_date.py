import datetime

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pytz import timezone
from sous_chef.date.get_due_date import (
    DEFAULT_TIMEZONE,
    DueDatetimeFormatter,
    MealTime,
    Weekday,
    get_weekday_index,
)
from tests.conftest import FROZEN_DATE

FROZEN_MONDAY = "2022-01-10"


@pytest.fixture
def config_get_due_date():
    with initialize(version_base=None, config_path="../../../config/date"):
        return compose(config_name="get_due_date").due_date


def create_datetime(
    day: int,
    year: int = 2022,
    month: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    tzinfo=timezone("UTC"),
):
    return datetime.datetime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        tzinfo=tzinfo,
    )


class TestExtendedEnum:
    @staticmethod
    @pytest.mark.parametrize(
        "string_method,expected_list",
        [
            ("casefold", ["breakfast", "lunch", "snack", "dinner", "dessert"]),
            ("lower", ["breakfast", "lunch", "snack", "dinner", "dessert"]),
            (
                "capitalize",
                ["Breakfast", "Lunch", "Snack", "Dinner", "Dessert"],
            ),
            ("upper", ["BREAKFAST", "LUNCH", "SNACK", "DINNER", "DESSERT"]),
        ],
    )
    def test_name_list(string_method, expected_list):
        assert MealTime.name_list(string_method) == expected_list


class TestWeekdayIndex:
    @staticmethod
    @pytest.mark.parametrize("weekday", Weekday)
    def test_check_index(frozen_due_datetime_formatter, weekday):
        assert get_weekday_index(weekday.name) == weekday.index

    @staticmethod
    @pytest.mark.parametrize("weekday", ["Monday", "moNDay", "MONDAY"])
    def test_alternate_capitalization(weekday):
        assert get_weekday_index(weekday) == 0


class TestDueDatetimeFormatter:
    @staticmethod
    @freeze_time(FROZEN_MONDAY)
    @pytest.mark.parametrize(
        "weekday,week_offset,expected_day",
        [
            (Weekday.monday, 0, 10),
            (Weekday.tuesday, 0, 11),
            (Weekday.wednesday, 0, 12),
            (Weekday.thursday, 0, 13),
            (Weekday.friday, 0, 14),
            (Weekday.saturday, 0, 15),
            (Weekday.sunday, 0, 16),
            (Weekday.monday, 1, 17),
            (Weekday.tuesday, 1, 18),
            (Weekday.wednesday, 1, 19),
            (Weekday.thursday, 1, 20),
            (Weekday.friday, 1, 21),
            (Weekday.saturday, 1, 22),
            (Weekday.sunday, 1, 23),
        ],
    )
    def test_get_anchor_date(
        config_get_due_date,
        weekday,
        week_offset,
        expected_day,
    ):
        anchor_day = weekday.name
        config_get_due_date.anchor_day = anchor_day
        config_get_due_date.week_offset = week_offset
        anchor_date = DueDatetimeFormatter(
            config=config_get_due_date
        ).get_anchor_date()
        assert anchor_date == datetime.date(
            year=2022, month=1, day=expected_day
        )
        assert anchor_date.weekday() == weekday.index

    @staticmethod
    def test_get_calendar_week(frozen_due_datetime_formatter):
        assert frozen_due_datetime_formatter.get_calendar_week() == 3

    @staticmethod
    def test_get_due_datetime_with_meal_time(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_meal_time(
            Weekday.monday.name, "dinner"
        ) == create_datetime(day=24, hour=16, minute=30)

    @staticmethod
    def test_get_due_datetime_with_time(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_time(
            Weekday.monday.name, time=MealTime.dinner.value
        ) == create_datetime(
            day=24, hour=16, minute=30, tzinfo=DEFAULT_TIMEZONE
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    @pytest.mark.parametrize(
        "weekday,week_offset,expected_day",
        [
            (Weekday.tuesday, -1, 11),
            (Weekday.wednesday, -1, 12),
            (Weekday.thursday, -1, 13),
            (Weekday.friday, 0, 14),
            (Weekday.saturday, 0, 15),
            (Weekday.sunday, 0, 16),
            (Weekday.monday, 0, 17),
            (Weekday.tuesday, 0, 18),
            (Weekday.wednesday, 0, 19),
            (Weekday.thursday, 0, 20),
            (Weekday.friday, 1, 21),
            (Weekday.saturday, 1, 22),
            (Weekday.sunday, 1, 23),
            (Weekday.monday, 1, 17),
            (Weekday.tuesday, 1, 18),
            (Weekday.wednesday, 1, 19),
            (Weekday.thursday, 1, 20),
        ],
    )
    def test__get_anchor_date_at_midnight(
        frozen_due_datetime_formatter, weekday, week_offset, expected_day
    ):
        frozen_due_datetime_formatter.anchor_day = weekday.name
        frozen_due_datetime_formatter.week_offset = week_offset
        assert (
            frozen_due_datetime_formatter._get_anchor_date_at_midnight()
            == create_datetime(expected_day)
        )

    @staticmethod
    @freeze_time(FROZEN_MONDAY)
    @pytest.mark.parametrize(
        "weekday,day",
        [
            (Weekday.wednesday, 19),
            (Weekday.thursday, 20),
            (Weekday.friday, 21),
            (Weekday.saturday, 22),
            (Weekday.sunday, 23),
            (Weekday.monday, 24),
            (Weekday.tuesday, 18),
        ],
    )
    def test_get_date_relative_to_anchor_tuesday(
        config_get_due_date, weekday, day
    ):
        config_get_due_date.anchor_day = Weekday.tuesday.name
        config_get_due_date.week_offset = 1
        assert DueDatetimeFormatter(
            config=config_get_due_date
        ).get_date_relative_to_anchor(weekday.name) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize(
        "weekday,day",
        [
            (Weekday.saturday, 22),
            (Weekday.sunday, 23),
            (Weekday.monday, 24),
            (Weekday.tuesday, 25),
            (Weekday.wednesday, 26),
            (Weekday.thursday, 27),
            (Weekday.friday, 21),
        ],
    )
    def test_get_date_relative_to_anchor_friday(
        frozen_due_datetime_formatter, weekday, day
    ):
        assert frozen_due_datetime_formatter.get_date_relative_to_anchor(
            weekday.name
        ) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize("hour,minute", [(0, 0), (1, 31), (23, 59)])
    def test__set_specified_time(frozen_due_datetime_formatter, hour, minute):
        initial_datetime = create_datetime(day=17)
        assert initial_datetime.hour == 0
        assert initial_datetime.minute == 0

        assert frozen_due_datetime_formatter._set_specified_time(
            initial_datetime,
            datetime.time(hour=hour, minute=minute, tzinfo=DEFAULT_TIMEZONE),
        ) == create_datetime(day=17, hour=hour, minute=minute)
