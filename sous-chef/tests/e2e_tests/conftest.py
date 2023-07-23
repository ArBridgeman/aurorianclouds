import pytest
from hydra import compose, initialize
from sous_chef.menu.record_menu_history import MenuHistorian
from tests.conftest import FROZEN_DATETIME

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


@pytest.fixture
def menu_history(gsheets_helper):
    with initialize(version_base=None, config_path="../../config/menu"):
        config = compose(config_name="record_menu_history").record_menu_history
        config.save_loc.worksheet = "tmp-menu-history"
        return MenuHistorian(
            config,
            gsheets_helper=gsheets_helper,
            current_menu_start_date=FROZEN_DATETIME,
        )


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)
