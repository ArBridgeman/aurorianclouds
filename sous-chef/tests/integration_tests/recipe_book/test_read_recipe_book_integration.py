import re
from typing import List, Tuple, Union

import pytest
from hydra import compose, initialize
from sous_chef.recipe_book.read_recipe_book import RecipeBook

LABEL_PATTERN = re.compile(r"^[\w\-/]+$")


@pytest.fixture
def recipe_book():
    with initialize(version_base=None, config_path="../../../config"):
        config = compose(config_name="recipe_book").recipe_book
        return RecipeBook(config)


@pytest.mark.dropbox
class TestRecipeBook:
    @staticmethod
    def _has_no_duplicates(value_list: Union[List, Tuple]):
        return len(set(value_list)) == len(value_list)

    @staticmethod
    def _has_no_space_label_tuple(label_tuple: Tuple):
        for label in label_tuple:
            if LABEL_PATTERN.match(label) is None:
                print(label)
                return False
        return True

    def test__read_category_tuple_quality_check(self, recipe_book):
        assert self._has_no_duplicates(recipe_book.category_tuple)
        assert self._has_no_space_label_tuple(recipe_book.category_tuple)

    def test__read_tag_tuple_quality_check(self, recipe_book):
        assert self._has_no_duplicates(recipe_book.tag_tuple)
        assert self._has_no_space_label_tuple(recipe_book.tag_tuple)
