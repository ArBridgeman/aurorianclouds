import pytest
from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.pantry_list.read_pantry_list import PantryList


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


@pytest.fixture(scope="module")
def pantry_list(gsheets_helper):
    with initialize(version_base=None, config_path="../../config/"):
        config = compose(config_name="pantry_list")
        return PantryList(config.pantry_list, gsheets_helper)


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)
