import pytest
from hydra import compose, initialize
from sous_chef.pantry_list.read_pantry_list import PantryList

from utilities.api.gsheets_api import GsheetsHelper


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../../config/api/"):
        config = compose(config_name="gsheets_api")
    return GsheetsHelper(config=config.gsheets)


@pytest.fixture(scope="module")
def pantry_list(gsheets_helper):
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="pantry_list")
    return PantryList(config=config.pantry_list, gsheets_helper=gsheets_helper)
