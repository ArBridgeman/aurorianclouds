from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.date.get_due_date import DueDatetimeFormatter, ExtendedEnum
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.recipe_book.read_recipe_book import RecipeBook

FROZEN_DATE = "2022-01-14"


class MockMealTime(ExtendedEnum):
    breakfast = {"hour": 8, "minute": 30}
    lunch = {"hour": 11, "minute": 30}
    snack = {"hour": 15, "minute": 00}
    dinner = {"hour": 18, "minute": 15}


@pytest.fixture
def mock_recipe_book():
    with initialize(version_base=None, config_path="../../config"):
        config = compose(config_name="recipe_book")
        with patch.object(RecipeBook, "__init__", lambda x, y, z: None):
            return Mock(RecipeBook(config, None))


@pytest.fixture
@freeze_time(FROZEN_DATE)
def frozen_due_datetime_formatter():
    due_datetime_formatter = DueDatetimeFormatter(anchor_day="Friday")
    due_datetime_formatter.meal_time = MockMealTime
    return due_datetime_formatter


@pytest.fixture
def unit_formatter():
    return UnitFormatter()
