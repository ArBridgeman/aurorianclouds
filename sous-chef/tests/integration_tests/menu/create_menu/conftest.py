import pytest
from hydra import compose, initialize

PROJECT = "Pytest-area"


@pytest.fixture
def config():
    with initialize(version_base=None, config_path="../../../../config/"):
        config = compose(config_name="menu_main")

        menu_config = config.menu.create_menu
        menu_config.final_menu.worksheet = "test-tmp-menu"
        menu_config.fixed.workbook = "test-fixed_menus"
        menu_config.fixed.menu_number = 1
        menu_config.todoist.project_name = PROJECT
        menu_config.fixed.already_in_future_menus.active = False
        return config


@pytest.fixture
def menu_config(config):
    return config.menu.create_menu
