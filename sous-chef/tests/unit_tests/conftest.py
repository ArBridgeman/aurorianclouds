from unittest.mock import Mock, patch

import pytest
from hydra import compose, initialize
from sous_chef.recipe_book.read_recipe_book import RecipeBook


@pytest.fixture
def mock_recipe_book():
    with initialize(version_base=None, config_path="../../config"):
        config = compose(config_name="recipe_book")
        with patch.object(RecipeBook, "__init__", lambda x, y, z: None):
            return Mock(RecipeBook(config, None))
