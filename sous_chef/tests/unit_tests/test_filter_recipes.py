import pytest
from sous_chef.filter_recipes import (
    create_tags_and_filter,
    has_recipe_category_or_tag,
)
from tests.conftest import RECIPES


@pytest.mark.parametrize(
    "recipe_tags,desired_tag,expected_result",
    [
        (["poultry"], "poultry", True),
        (["BBQ", "American", "beef"], "American", True),
        (["French"], "American", False),
    ],
)
def test_has_recipe_category_or_tag(recipe_tags, desired_tag, expected_result):
    assert (
        has_recipe_category_or_tag(recipe_tags, desired_tag) == expected_result
    )


@pytest.mark.parametrize(
    "desired_tags,expected_result",
    [(["poultry", "American"], [True]), (["poultry", "Italian"], [False])],
)
def test_create_tags_and_filter(desired_tags, expected_result):
    result = create_tags_and_filter(RECIPES, desired_tags)
    assert result.values == expected_result
