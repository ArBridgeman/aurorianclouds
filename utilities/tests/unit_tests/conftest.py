import pytest
from hydra import compose, initialize

from utilities.testing.todoist import TestTodoistHelper


@pytest.fixture(scope="module")
def config():
    with initialize(version_base=None, config_path="../../config/api"):
        yield compose(config_name="todoist_api")


@pytest.fixture(scope="module")
def test_todoist_helper(config):
    return TestTodoistHelper(config=config)
