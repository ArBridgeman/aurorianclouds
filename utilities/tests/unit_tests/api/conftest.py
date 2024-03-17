from unittest.mock import patch

import pytest
from api.todoist_api import TodoistHelper


@pytest.fixture(scope="module")
def mock_todoist_helper(config):
    with patch.object(TodoistHelper, TodoistHelper.__post_init__.__name__):
        return TodoistHelper(config)


# fixture to iterate over other fixtures
@pytest.fixture(params=["mock_todoist_helper", "test_todoist_helper"])
def todoist_helper(request):
    return request.getfixturevalue(request.param)
