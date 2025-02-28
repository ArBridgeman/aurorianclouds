from copy import deepcopy
from unittest.mock import Mock

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from tests.conftest import FROZEN_DATE, FROZEN_DAY, MockMealTime
from tests.data.util_data import get_local_recipe_book_path

from utilities.api.todoist_api import TodoistHelper

PROJECT = "Pytest-area"


@pytest.fixture(scope="module")
def fixed_grocery_config():
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="grocery_list")

    config.recipe_book.path = get_local_recipe_book_path()

    menu_config = config.menu.create_menu
    menu_config.final_menu.worksheet = "unused"
    menu_config.fixed.workbook = "unused"
    menu_config.fixed.menu_number = 1
    menu_config.fixed.already_in_future_menus.active = False
    menu_config.todoist.project_name = PROJECT

    due_config = config.date.due_date
    due_config.anchor_day = FROZEN_DAY
    due_config.week_offset = 1

    grocery_config = config.grocery_list
    grocery_config.preparation.project_name = "Pytest-area"
    grocery_config.todoist.remove_existing_prep_task = True

    original = deepcopy(config)

    yield config

    assert config == original, "fixed_config should not be modified"


@pytest.fixture(scope="module")
@freeze_time(FROZEN_DATE)
def frozen_due_datetime_formatter(fixed_grocery_config):
    due_datetime_formatter = DueDatetimeFormatter(
        config=fixed_grocery_config.date.due_date
    )
    due_datetime_formatter.meal_time = MockMealTime
    return due_datetime_formatter


@pytest.fixture
def mock_ingredient_field(fixed_grocery_config):
    return Mock(
        IngredientField(
            config=fixed_grocery_config.formatter.get_ingredient_field,
            ingredient_formatter=None,
            recipe_book=None,
        )
    )


@pytest.fixture(scope="module")
def todoist_helper(fixed_grocery_config):
    return TodoistHelper(fixed_grocery_config.api.todoist)
