import pandas as pd


def assert_equal_dataframe(df1: pd.DataFrame, df2: pd.DataFrame):
    assert pd.testing.assert_frame_equal(df1, df2, check_dtype=False) is None


def assert_equal_series(s1: pd.Series, s2: pd.Series):
    assert pd.testing.assert_series_equal(s1, s2) is None
