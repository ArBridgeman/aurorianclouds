import pandas as pd
import pytest
from sous_chef.read_recipes import create_timedelta


@pytest.mark.parametrize(
    "input_time_string,expected_timedelta",
    [
        ("hurr 30 min", pd.to_timedelta("00:30:00")),
        ("20 min 10 s", pd.to_timedelta("00:20:10")),
        ("0:10", pd.to_timedelta("00:10:00")),
        ("5 hours", pd.to_timedelta("05:00:00")),
    ],
)
def test_create_timedelta(input_time_string, expected_timedelta):
    assert create_timedelta(input_time_string) == expected_timedelta
