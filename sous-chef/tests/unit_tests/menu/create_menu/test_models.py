import pytest
from sous_chef.menu.create_menu.models import get_weekday_from_short


class TestGetWeekdayFromShort:
    @staticmethod
    @pytest.mark.parametrize(
        "short_day,expected_week_day",
        [("sat", "Saturday"), ("Mon", "Monday"), ("THU", "Thursday")],
    )
    def test_expected_values_succeed(short_day, expected_week_day):
        assert get_weekday_from_short(short_day) == expected_week_day

    @staticmethod
    def test__unknown_date_raise_error():
        # derived exception MenuConfigError
        with pytest.raises(Exception) as error:
            get_weekday_from_short("not-a-day")
        assert str(error.value) == "[menu config error] not-a-day unknown day!"
