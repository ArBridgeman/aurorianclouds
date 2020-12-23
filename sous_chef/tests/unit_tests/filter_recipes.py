import pytest

from conftest import RECIPES
from sous_chef.sous_chef.filter_recipes import has_recipe_category_or_tag, create_tags_and_filter


@pytest.mark.parametrize("recipe_tags,desired_tag,expected_result",
                         [(["poultry"], "poultry", True),
                          (["BBQ", "American", "beef"], "American", True),
                          (["French"], "American", False)])
def test_check_recipe_for_tag(recipe_tags, desired_tag, expected_result):
    assert has_recipe_category_or_tag(recipe_tags, desired_tag) == expected_result


@pytest.mark.parametrize("desired_tags,expected_result",
                         [(["poultry", "American"], [True]),
                          (["poultry", "Italian"], [False])])
def test_create_tags_and_filter(desired_tags, expected_result):
    result = create_tags_and_filter(RECIPES, desired_tags)
    assert result.values == expected_result
