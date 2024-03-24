from unittest.mock import patch

import pytest

from utilities.api.todoist_api import TodoistHelper


@pytest.fixture(scope="module")
def mock_todoist_helper(todoist_config):
    with patch.object(TodoistHelper, TodoistHelper.__post_init__.__name__):
        return TodoistHelper(todoist_config)


# fixture to iterate over other fixtures
@pytest.fixture(params=["mock_todoist_helper", "debug_todoist_helper"])
def todoist_helper(request):
    return request.getfixturevalue(request.param)
