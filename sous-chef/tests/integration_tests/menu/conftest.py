from copy import deepcopy

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.date.get_due_date import DueDatetimeFormatter
from tests.conftest import FROZEN_DATE, FROZEN_DAY, MockMealTime
from tests.data.util_data import get_local_recipe_book_path

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper

PROJECT = "Pytest-area"


@pytest.fixture(scope="module")
def fixed_menu_config():
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="menu_main")

    config.recipe_book.path = get_local_recipe_book_path()

    menu_config = config.menu.create_menu
    menu_config.final_menu.worksheet = "test-tmp-menu"
    menu_config.fixed.workbook = "test-fixed_menus"
    menu_config.fixed.menu_number = 1
    menu_config.fixed.already_in_future_menus.active = False
    menu_config.todoist.project_name = PROJECT

    due_config = config.date.due_date
    due_config.anchor_day = FROZEN_DAY
    due_config.week_offset = 1

    menu_history_config = config.menu.record_menu_history
    menu_history_config.save_loc.worksheet = "tmp-menu-history"

    original = deepcopy(config)

    yield config

    assert config == original, "fixed_config should not be modified"


@pytest.fixture
def config(fixed_menu_config):
    return deepcopy(fixed_menu_config)


@pytest.fixture
def menu_config(config):
    return config.menu.create_menu


@pytest.fixture(scope="module")
@freeze_time(FROZEN_DATE)
def frozen_due_datetime_formatter(fixed_menu_config):
    due_datetime_formatter = DueDatetimeFormatter(
        config=fixed_menu_config.date.due_date
    )
    due_datetime_formatter.meal_time = MockMealTime
    return due_datetime_formatter


@pytest.fixture(scope="module")
def gsheets_helper(fixed_menu_config):
    return GsheetsHelper(fixed_menu_config.api.gsheets)


@pytest.fixture(scope="module")
def todoist_helper(fixed_menu_config):
    return TodoistHelper(fixed_menu_config.api.todoist)
