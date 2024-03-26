from unittest.mock import patch

import pytest

from utilities.api.todoist_api import TodoistHelper


@pytest.fixture(scope="module")
def mock_todoist_helper(todoist_config):
    with patch.object(TodoistHelper, TodoistHelper.__post_init__.__name__):
        return TodoistHelper(todoist_config)
