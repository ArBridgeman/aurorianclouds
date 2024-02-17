from datetime import timedelta

import pytest
from jellyfin_helpers.workout_plan.date_util import (
    RelativeDate,
    convert_datetime_to_enum,
)
from jellyfin_helpers.workout_plan.models import Day


@pytest.mark.parametrize(
    "plus_day, expectation",
    [
        (0, Day.sun),
        (1, Day.mon),
        (2, Day.tue),
        (3, Day.wed),
        (4, Day.thu),
        (5, Day.fri),
        (6, Day.sat),
    ],
)
def test_convert_datetime_to_enum(today, plus_day, expectation):
    datetime_considered = today + timedelta(days=plus_day)
    assert convert_datetime_to_enum(datetime_considered) == expectation


@pytest.mark.parametrize(
    "plus_day, expectation",
    [
        pytest.param(0, 1, id="run_on_sun_add_1_for_mon"),
        pytest.param(1, 0, id="run_on_mon_add_0_for_mon"),
        pytest.param(2, 6, id="run_on_tues_add_6_for_mon"),
        pytest.param(3, 5, id="run_on_wed_add_5_for_mon"),
        pytest.param(4, 4, id="run_on_thur_add_4_for_mon"),
        pytest.param(5, 3, id="run_on_fri_add_3_for_mon"),
        pytest.param(-1, 2, id="run_on_sat_add_2_for_mon"),
    ],
)
def test_get_days_from_now_1_is_always_next_monday(
    today, plus_day, expectation
):
    days_from_now = RelativeDate()
    # frozen date is a Sunday
    days_from_now.today_index = convert_datetime_to_enum(today).value + plus_day
    # want entry #1 to always be the next future/same Monday
    assert days_from_now.get_days_from_now(day_index=1) == expectation


@pytest.mark.parametrize("day_index", list(range(5)))
def test_get_days_from_sunday(today, day_index):
    days_from_now = RelativeDate()
    # frozen date is a Sunday
    days_from_now.today_index = convert_datetime_to_enum(today).value
    # want entry #1 to always be the next future/same Monday
    assert days_from_now.get_days_from_now(day_index=day_index) == day_index


@pytest.mark.parametrize("day_index", list(range(5)))
def test_get_days_from_friday(today, day_index):
    days_from_now = RelativeDate()
    # frozen date is a Sunday, so would be Friday
    days_from_now.today_index = convert_datetime_to_enum(today).value - 2
    # want entry #1 to always be the next future/same Monday
    assert days_from_now.get_days_from_now(day_index=day_index) == day_index + 2
