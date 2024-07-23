from dataclasses import dataclass
from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pytz import UTC
from sous_chef.abstract.extended_enum import ExtendedEnum
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from sous_chef.grocery_list.generate_grocery_list.generate_grocery_list import (
    GroceryList,
)
from sous_chef.nutrition.provide_nutritional_info import Nutritionist
from sous_chef.recipe_book.read_recipe_book import RecipeBook

FROZEN_DATE = "2022-01-14"
FROZEN_DATETIME = datetime.strptime(FROZEN_DATE, "%Y-%m-%d").replace(tzinfo=UTC)
FROZEN_DAY = pd.to_datetime(FROZEN_DATE).day_name()


@pytest.fixture
def config_recipe_book():
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="recipe_book").recipe_book


class MockMealTime(ExtendedEnum):
    breakfast = {"hour": 8, "minute": 30}
    lunch = {"hour": 12, "minute": 00}
    snack = {"hour": 15, "minute": 00}
    dinner = {"hour": 16, "minute": 30}
    dessert = {"hour": 19, "minute": 30}


@dataclass
class Recipe:
    title: str
    min_prep_time: int
    min_cook_time: int
    quantity: str
    is_favorite: bool
    rating: int
    tags: list


recipe1 = Recipe(
    "Bourbon Chicken",
    10,
    30,
    "4 servings",
    False,
    0,
    ["poultry", "American", "BBQ"],
)

RECIPES = pd.DataFrame([recipe1])


@pytest.fixture
def config_grocery_list():
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="grocery_list").grocery_list


@pytest.fixture
def config_due_date():
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="grocery_list").date.due_date


@pytest.fixture
@freeze_time(FROZEN_DATE)
def frozen_due_datetime_formatter(config_due_date):
    config_due_date.anchor_day = FROZEN_DAY
    config_due_date.week_offset = 1
    due_datetime_formatter = DueDatetimeFormatter(config=config_due_date)
    due_datetime_formatter.meal_time = MockMealTime
    return due_datetime_formatter


@pytest.fixture
@freeze_time(FROZEN_DATE)
def grocery_list(
    config_grocery_list,
    unit_formatter,
    mock_ingredient_field,
    frozen_due_datetime_formatter,
):
    grocery_list = GroceryList(
        config=config_grocery_list,
        due_date_formatter=frozen_due_datetime_formatter,
        unit_formatter=unit_formatter,
        ingredient_field=mock_ingredient_field,
    )
    grocery_list.second_shopping_day_group = ["vegetables"]
    return grocery_list


@pytest.fixture
def mock_ingredient_field():
    with initialize(version_base=None, config_path="../config/formatter"):
        config = compose(config_name="get_ingredient_field")
        return Mock(IngredientField(config.get_ingredient_field, None, None))


@pytest.fixture
def mock_ingredient_formatter():
    with initialize(version_base=None, config_path="../config/formatter"):
        config = compose(config_name="format_ingredient")
        return Mock(IngredientFormatter(config, None, None))


@pytest.fixture
def mock_recipe_book():
    with initialize(version_base=None, config_path="../config"):
        config = compose(config_name="recipe_book")
        with patch.object(RecipeBook, "__post_init__", lambda x: None):
            return Mock(RecipeBook(config, None))


@pytest.fixture
def nutritionist():
    with initialize(version_base=None, config_path="../config/"):
        config = compose(config_name="nutrition").nutrition
        config.sheet_name = "nutrition-test"
        return Nutritionist(config=config)


@pytest.fixture
def unit_formatter():
    return UnitFormatter()
