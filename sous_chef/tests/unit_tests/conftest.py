from unittest.mock import Mock, patch

import pytest
from hydra import compose, initialize
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from tests.util import RecipeBuilder


@pytest.fixture
def mock_recipe_book():
    with initialize(config_path="../../config"):
        config = compose(config_name="recipe_book")
        with patch.object(RecipeBook, "__init__", lambda x, y, z: None):
            return Mock(RecipeBook(config, None))


@pytest.fixture
def recipe_with_recipe_title(recipe_title):
    return RecipeBuilder().with_recipe_title(recipe_title).build()


@pytest.fixture
def unit_formatter():
    return UnitFormatter()
