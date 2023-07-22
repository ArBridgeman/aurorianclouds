import pytest
from hydra import compose, initialize

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../../config/api"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../../config/api"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)
