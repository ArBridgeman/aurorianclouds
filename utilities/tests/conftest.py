import pytest
from hydra import compose, initialize

from utilities.testing.todoist import DebugTodoistHelper, LocalTodoistConnection

DEFAULT_PROJECT = "Pytest-area"
DEFAULT_SECTION = "Test-section"


@pytest.fixture(scope="module")
def default_project():
    return DEFAULT_PROJECT


@pytest.fixture(scope="module")
def default_section():
    return DEFAULT_SECTION


@pytest.fixture(scope="module")
def todoist_config():
    with initialize(version_base=None, config_path="../config/api"):
        yield compose(config_name="todoist_api").todoist


@pytest.fixture(scope="module")
def local_todoist_project_id():
    return 1


@pytest.fixture(scope="module")
def local_todoist_connection(
    default_project, default_section, local_todoist_project_id
):
    local_todoist_connection = LocalTodoistConnection()

    default_project_id = local_todoist_connection.add_project(
        default_project, project_id=local_todoist_project_id
    )
    local_todoist_connection.add_project("menu")
    local_todoist_connection.add_project("groceries")

    local_todoist_connection.add_section(
        section_name=default_section, project_id=default_project_id
    )

    return local_todoist_connection


@pytest.fixture(scope="module")
def debug_todoist_helper(todoist_config, local_todoist_connection):
    debug_todoist_helper = DebugTodoistHelper(config=todoist_config)
    debug_todoist_helper.set_connection(local_todoist_connection)
    return debug_todoist_helper
