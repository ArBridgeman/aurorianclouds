import collections
import re
from typing import List, Tuple, Union

import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.recipe_book.read_recipe_book import RecipeBook

LABEL_PATTERN = re.compile(r"^[\w\-/]+$")


@pytest.fixture
def recipe_book():
    with initialize(version_base=None, config_path="../../../config"):
        config = compose(config_name="recipe_book").recipe_book
        config.deduplicate = False
        return RecipeBook(config)


@pytest.mark.dropbox
class TestRecipeBook:
    @staticmethod
    def _has_no_duplicates(value_list: Union[List, Tuple]):
        return len(set(value_list)) == len(value_list)

    @staticmethod
    def _has_no_space_label_tuple(label_tuple: Tuple):
        no_space_label = True
        for label in label_tuple:
            if LABEL_PATTERN.match(label) is None:
                print(label)
                no_space_label = False
        return no_space_label

    @staticmethod
    def _has_no_unused_label(label_col: pd.Series, label_tuple: Tuple):
        used_labels = collections.Counter(label_col.explode().values)
        if np.NaN in used_labels.keys():
            used_labels.pop(np.NaN)
        unused_labels = set(label_tuple) - set(used_labels.keys())
        if has_unused_labels := (len(unused_labels) > 0):
            print("# unused labels")
            print(unused_labels)
        return not has_unused_labels

    def test__read_category_tuple_quality_check(self, recipe_book):
        assert self._has_no_duplicates(recipe_book.category_tuple)
        assert self._has_no_space_label_tuple(recipe_book.category_tuple)
        assert self._has_no_unused_label(
            recipe_book.dataframe.categories, recipe_book.category_tuple
        )

    def test__read_tag_tuple_quality_check(self, recipe_book):
        assert self._has_no_duplicates(recipe_book.tag_tuple)
        assert self._has_no_space_label_tuple(recipe_book.tag_tuple)
        assert self._has_no_unused_label(
            recipe_book.dataframe.tags, recipe_book.tag_tuple
        )

    def test_recipe_book_has_no_missing_category(self, recipe_book):
        mask_missing_category = ~recipe_book.dataframe.categories.astype(bool)
        if has_missing_category := any(mask_missing_category):
            print(
                recipe_book.dataframe[mask_missing_category][
                    ["title"]
                ].sort_values(by=["title"])
            )
        assert not has_missing_category

    @pytest.mark.skip(
        reason=">300 lack tags; enact after recipe standardizer created"
    )
    def test_recipe_book_has_no_missing_tag(self, recipe_book):
        mask_missing_tag = ~recipe_book.dataframe.tags.astype(bool)
        if has_missing_tag := any(mask_missing_tag):
            print(
                recipe_book.dataframe[mask_missing_tag][["title"]].sort_values(
                    by=["title"]
                )
            )
        assert not has_missing_tag

    def test_recipe_book_no_duplicate_recipe_titles(self, recipe_book):
        mask_duplicates = recipe_book.dataframe.duplicated(
            subset=["title"], keep="first"
        )
        if has_duplicates := any(mask_duplicates):
            print(
                recipe_book.dataframe[mask_duplicates][["title"]].sort_values(
                    by=["title"]
                )
            )
        assert not has_duplicates

    def test_recipe_book_no_duplicate_urls(self, recipe_book):
        mask_is_url = recipe_book.dataframe.url.str.strip().str.startswith(
            "http"
        )
        mask_duplicates = recipe_book.dataframe.duplicated(
            subset=["url"], keep=False
        )
        mask_all = mask_is_url & mask_duplicates
        if has_duplicates := any(mask_all):
            print(
                recipe_book.dataframe[mask_all][["title", "url"]].sort_values(
                    by=["url"]
                )
            )
        assert not has_duplicates
