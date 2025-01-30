from pathlib import Path

import pytest
from hydra import compose, initialize
from sous_chef.menu.record_menu_history import MenuHistorian
from tests.conftest import FROZEN_DATETIME
from tests.data.util_data import get_local_recipe_book_path

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper

abs_path = Path(__file__).parent.absolute()

PROJECT = "Pytest-area"


def get_config(config_name: str):
    with initialize(version_base=None, config_path="../../config"):
        config = compose(config_name=config_name)

        config.recipe_book.path = get_local_recipe_book_path()

        create_menu = config.menu.create_menu
        create_menu.final_menu.worksheet = "test-tmp-menu"
        create_menu.fixed.workbook = "test-fixed_menus"
        create_menu.fixed.basic_number = 0
        create_menu.fixed.menu_number = 1
        create_menu.todoist.project_name = PROJECT
        create_menu.todoist.is_active = True

    return config


@pytest.fixture(scope="module")
def menu_config():
    config = get_config("menu_main")
    config.menu.create_menu.fixed.already_in_future_menus.num_weeks = 1
    config.menu.record_menu_history.save_loc.worksheet = "tmp-menu-history"
    return config


@pytest.fixture(scope="module")
def grocery_config():
    config = get_config("grocery_list")
    config.grocery_list.preparation.project_name = PROJECT
    config.grocery_list.todoist.project_name = PROJECT
    config.grocery_list.run_mode.with_todoist = True
    config.grocery_list.run_mode.check_referenced_recipe = False
    return config


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="gsheets_api")
    return GsheetsHelper(config.gsheets)


@pytest.fixture(scope="module")
def menu_history(menu_config, gsheets_helper):
    return MenuHistorian(
        config=menu_config.menu.record_menu_history,
        gsheets_helper=gsheets_helper,
        current_menu_start_date=FROZEN_DATETIME,
    )


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="todoist_api")
    return TodoistHelper(config.todoist)
