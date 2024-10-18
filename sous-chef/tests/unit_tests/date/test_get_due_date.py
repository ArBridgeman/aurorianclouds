import datetime

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pytz import timezone
from sous_chef.date.get_due_date import (
    DEFAULT_TIMEZONE,
    DueDatetimeFormatter,
    MealTime,
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
    @freeze_time(FROZEN_MONDAY)
    @pytest.mark.parametrize(
        "anchor_day,week_offset,expected_day,expected_index",
        [
            ("Monday", 0, 10, 0),
            ("Tuesday", 0, 11, 1),
            ("Wednesday", 0, 12, 2),
            ("Thursday", 0, 13, 3),
            ("Friday", 0, 14, 4),
            ("Saturday", 0, 15, 5),
            ("Sunday", 0, 16, 6),
            ("Monday", 1, 17, 0),
            ("Tuesday", 1, 18, 1),
            ("Wednesday", 1, 19, 2),
            ("Thursday", 1, 20, 3),
            ("Friday", 1, 21, 4),
            ("Saturday", 1, 22, 5),
            ("Sunday", 1, 23, 6),
        ],
    )
    def test_get_anchor_date(
        config_get_due_date,
        anchor_day,
        week_offset,
        expected_day,
        expected_index,
    ):
        config_get_due_date.anchor_day = anchor_day
        config_get_due_date.week_offset = week_offset
        anchor_date = DueDatetimeFormatter(
            config=config_get_due_date
        ).get_anchor_date()
        assert anchor_date == datetime.date(
            year=2022, month=1, day=expected_day
        )
        assert anchor_date.weekday() == expected_index

    @staticmethod
    def test_get_calendar_week(frozen_due_datetime_formatter):
        assert frozen_due_datetime_formatter.get_calendar_week() == 3

    @staticmethod
    def test_get_due_datetime_with_meal_time(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_meal_time(
            "monday", "dinner"
        ) == create_datetime(day=24, hour=16, minute=30)

    @staticmethod
    def test_get_due_datetime_with_time(
        frozen_due_datetime_formatter,
    ):
        assert frozen_due_datetime_formatter.get_due_datetime_with_time(
            "monday", time=MealTime.dinner.value
        ) == create_datetime(
            day=24, hour=16, minute=30, tzinfo=DEFAULT_TIMEZONE
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    @pytest.mark.parametrize(
        "weekday,week_offset,expected_day",
        [
            ("tuesday", -1, 11),
            ("wednesday", -1, 12),
            ("thursday", -1, 13),
            ("friday", 0, 14),
            ("saturday", 0, 15),
            ("sunday", 0, 16),
            ("monday", 0, 17),
            ("tuesday", 0, 18),
            ("wednesday", 0, 19),
            ("thursday", 0, 20),
            ("friday", 1, 21),
            ("saturday", 1, 22),
            ("sunday", 1, 23),
            ("monday", 1, 17),
            ("tuesday", 1, 18),
            ("wednesday", 1, 19),
            ("thursday", 1, 20),
        ],
    )
    def test__get_anchor_date_at_midnight(
        frozen_due_datetime_formatter, weekday, week_offset, expected_day
    ):
        frozen_due_datetime_formatter.anchor_day = weekday
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
            ("wednesday", 19),
            ("thursday", 20),
            ("friday", 21),
            ("saturday", 22),
            ("sunday", 23),
            ("monday", 24),
            ("tuesday", 18),
        ],
    )
    def test_get_date_relative_to_anchor_tuesday(
        config_get_due_date, weekday, day
    ):
        config_get_due_date.anchor_day = "Tuesday"
        config_get_due_date.week_offset = 1
        assert DueDatetimeFormatter(
            config=config_get_due_date
        ).get_date_relative_to_anchor(weekday) == create_datetime(day=day)

    @staticmethod
    @pytest.mark.parametrize(
        "weekday,day",
        [
            ("saturday", 22),
            ("sunday", 23),
            ("monday", 24),
            ("tuesday", 25),
            ("wednesday", 26),
            ("thursday", 27),
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
    @pytest.mark.parametrize("hour,minute", [(0, 0), (1, 31), (23, 59)])
    def test__set_specified_time(frozen_due_datetime_formatter, hour, minute):
        initial_datetime = create_datetime(day=17)
        assert initial_datetime.hour == 0
        assert initial_datetime.minute == 0

        assert frozen_due_datetime_formatter._set_specified_time(
            initial_datetime,
            datetime.time(hour=hour, minute=minute, tzinfo=DEFAULT_TIMEZONE),
        ) == create_datetime(day=17, hour=hour, minute=minute)
