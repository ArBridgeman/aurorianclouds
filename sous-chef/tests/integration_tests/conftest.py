from unittest.mock import patch

import pytest
from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from tests.data.util_data import get_local_recipe_book_path


@pytest.fixture
def local_recipe_book(config_recipe_book):
    with patch.object(RecipeBook, "__post_init__", return_value=None):
        recipe_book = RecipeBook(config_recipe_book)
        recipe_book.recipe_book_path = get_local_recipe_book_path()
        recipe_book._read_recipe_book()
        recipe_book._read_category_tuple()
        recipe_book._read_tag_tuple()
    return recipe_book


@pytest.fixture(scope="module")
def gsheets_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


@pytest.fixture(scope="module")
def pantry_list(gsheets_helper):
    with initialize(version_base=None, config_path="../../config/"):
        config = compose(config_name="pantry_list")
        return PantryList(config.pantry_list, gsheets_helper)


@pytest.fixture(scope="module")
def todoist_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="todoist_api")
        return TodoistHelper(config.todoist)
