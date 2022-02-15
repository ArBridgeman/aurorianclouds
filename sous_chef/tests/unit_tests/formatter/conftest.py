from unittest.mock import Mock, patch

import pytest
from hydra import compose, initialize
from pandas import Series
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.pantry_list.read_pantry_list import PantryList


def setup_ingredient_formatter(pantry_list, unit_formatter):
    with initialize(config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return IngredientFormatter(
            config=config.format_ingredient,
            pantry_list=pantry_list,
            unit_formatter=unit_formatter,
        )


@pytest.fixture
def mock_pantry_list():
    with initialize(config_path="../../../config"):
        config = compose(config_name="pantry_list")
        with patch.object(PantryList, "__init__", lambda x, y, z: None):
            return Mock(PantryList(config, None))


@pytest.fixture
def pantry_entry(
    item: str,
    skip: str,
):
    return Series(
        {
            "true_ingredient": item,
            "is_staple": False,
            "ingredient": item,
            "group": "Prepared",
            "item_plural": "s",
            "store": "grocery store",
            "skip": skip,
        }
    )


@pytest.fixture
def unit_formatter():
    return UnitFormatter()


@pytest.fixture
def ingredient_formatter(mock_pantry_list, unit_formatter):
    return setup_ingredient_formatter(mock_pantry_list, unit_formatter)


@pytest.fixture
def ingredient_formatter_find_pantry_entry(
    mock_pantry_list, unit_formatter, pantry_entry
):
    mock_pantry_list.retrieve_match.return_value = pantry_entry
    return setup_ingredient_formatter(mock_pantry_list, unit_formatter)


@pytest.fixture
def ingredient_formatter_with_pantry_error(
    mock_pantry_list, unit_formatter, error_arg
):
    mock_pantry_list.retrieve_match.side_effect = error_arg
    return setup_ingredient_formatter(mock_pantry_list, unit_formatter)
