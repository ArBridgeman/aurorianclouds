import pandas as pd
from sous_chef.recipe_book.read_recipe_book import Recipe


def assert_equal_dataframe(df1: pd.DataFrame, df2: pd.DataFrame):
    assert pd.testing.assert_frame_equal(df1, df2, check_dtype=False) is None


def assert_equal_series(s1: pd.Series, s2: pd.Series):
    assert pd.testing.assert_series_equal(s1, s2) is None


def create_recipe(
    title="dummy_title",
    rating=0.0,
    total_cook_time_str="5 minutes",
    ingredient_field="1 dummy text",
    factor=1.0,
):
    return Recipe(
        title=title,
        rating=rating,
        total_cook_time=pd.to_timedelta(total_cook_time_str),
        ingredient_field=ingredient_field,
        factor=factor,
    )
