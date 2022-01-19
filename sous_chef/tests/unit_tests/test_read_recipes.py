import pandas as pd
import pytest
from sous_chef.recipe_book.read_recipe_book import create_timedelta


@pytest.mark.parametrize(
    "input_time_string,expected_timedelta",
    [
        ("hurr 30 min", pd.to_timedelta("00:30:00")),
        ("20 min 10 s", pd.to_timedelta("00:20:10")),
        ("0:10", pd.to_timedelta("00:10:00")),
        ("0:10:0", pd.to_timedelta("00:10:00")),
        ("0:10:00", pd.to_timedelta("00:10:00")),
        ("00:10:00", pd.to_timedelta("00:10:00")),
        ("00:10:0", pd.to_timedelta("00:10:00")),
        ("5 hours", pd.to_timedelta("05:00:00")),
        ("15 minutes", pd.to_timedelta("00:15:00")),
        ("5 hours 10 mins", pd.to_timedelta("05:10:00")),
        ("prep time 6 min", pd.to_timedelta("00:06:00")),
    ],
)
def test_create_timedelta(input_time_string, expected_timedelta):
    assert create_timedelta(input_time_string) == expected_timedelta
