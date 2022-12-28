from unittest.mock import patch

import pytest
from hydra import compose, initialize
from sous_chef.messaging.todoist_api import TodoistHelper


@pytest.fixture
def mock_todoist_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="todoist_api")
        with patch.object(TodoistHelper, "__post_init__", lambda x: None):
            return TodoistHelper(config)
