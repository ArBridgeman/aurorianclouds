import pytest
from hydra import compose, initialize
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from tests.data.util_data import get_local_recipe_book_path

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


@pytest.fixture
def local_recipe_book(config_recipe_book):
    config_recipe_book.path = get_local_recipe_book_path()
    return RecipeBook(config_recipe_book)


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


@pytest.fixture(scope="module")
def pantry_list(gsheets_helper):
    with initialize(version_base=None, config_path="../../config/"):
        config = compose(config_name="pantry_list")
        return PantryList(config.pantry_list, gsheets_helper)


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)
