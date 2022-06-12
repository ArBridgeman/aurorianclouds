import pytest
from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)
