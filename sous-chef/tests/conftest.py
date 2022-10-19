from dataclasses import dataclass
from unittest.mock import Mock

import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.date.get_due_date import DueDatetimeFormatter, ExtendedEnum
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
)
from sous_chef.grocery_list.generate_grocery_list import GroceryList
from sous_chef.nutrition.provide_nutritional_info import Nutritionist

FROZEN_DATE = "2022-01-14"


class MockMealTime(ExtendedEnum):
    breakfast = {"hour": 8, "minute": 30}
    lunch = {"hour": 11, "minute": 30}
    snack = {"hour": 15, "minute": 00}
    dinner = {"hour": 18, "minute": 15}


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
@freeze_time(FROZEN_DATE)
def frozen_due_datetime_formatter():
    due_datetime_formatter = DueDatetimeFormatter(anchor_day="Friday")
    due_datetime_formatter.meal_time = MockMealTime
    return due_datetime_formatter


@pytest.fixture
def grocery_list(
    config_grocery_list,
    unit_formatter,
    mock_ingredient_field_formatter,
    frozen_due_datetime_formatter,
):
    grocery_list = GroceryList(
        config=config_grocery_list,
        unit_formatter=unit_formatter,
        ingredient_field_formatter=mock_ingredient_field_formatter,
    )
    grocery_list.date_formatter = frozen_due_datetime_formatter
    grocery_list.second_shopping_day_group = ["vegetables"]
    return grocery_list


@pytest.fixture
def mock_ingredient_field_formatter():
    with initialize(version_base=None, config_path="../config/formatter"):
        config = compose(config_name="format_ingredient_field")
        return Mock(IngredientFieldFormatter(config, None, None))


@pytest.fixture
def nutritionist():
    with initialize(version_base=None, config_path="../config/"):
        config = compose(config_name="nutrition").nutrition
        config.sheet_name = "nutrition-test"
        return Nutritionist(config=config)


@pytest.fixture
def unit_formatter():
    return UnitFormatter()
