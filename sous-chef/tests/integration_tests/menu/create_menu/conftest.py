import pytest
from hydra import compose, initialize

PROJECT = "Pytest-area"


@pytest.fixture
def menu_config():
    with initialize(version_base=None, config_path="../../../../config/menu"):
        config = compose(config_name="create_menu").create_menu
        config.final_menu.worksheet = "test-tmp-menu"
        config.fixed.workbook = "test-fixed_menus"
        config.fixed.menu_number = 1
        config.todoist.project_name = PROJECT
        config.fixed.already_in_future_menus.active = False
        return config
