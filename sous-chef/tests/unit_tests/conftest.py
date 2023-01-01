from unittest.mock import Mock, patch

import pytest
from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper


@pytest.fixture
def mock_gsheets():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        with patch.object(GsheetsHelper, "__post_init__"):
            return Mock(GsheetsHelper(config))


@pytest.fixture
def mock_todoist_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="todoist_api")
        with patch.object(TodoistHelper, "__post_init__", lambda x: None):
            return TodoistHelper(config)
