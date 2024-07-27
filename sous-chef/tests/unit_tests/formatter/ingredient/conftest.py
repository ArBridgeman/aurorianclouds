from unittest.mock import Mock, patch

import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.pantry_list.read_pantry_list import PantryList


@pytest.fixture
def ingredient_formatter(mock_pantry_list, unit_formatter):
    with initialize(
        version_base=None, config_path="../../../../config/formatter"
    ):
        config = compose(config_name="format_ingredient")
        return IngredientFormatter(
            config=config.format_ingredient,
            pantry_list=mock_pantry_list,
            unit_formatter=unit_formatter,
        )


@pytest.fixture
def mock_pantry_list():
    with initialize(version_base=None, config_path="../../../../config"):
        config = compose(config_name="pantry_list")
        with patch.object(PantryList, "__init__", lambda x, y, z: None):
            return Mock(PantryList(config, None))


@pytest.fixture
def pantry_entry(
    item: str,
):
    return pd.Series(
        {
            "true_ingredient": item,
            "ingredient": item,
            "group": "Canned",
            "item_plural": "s",
            "store": "grocery store",
            "label": "basic_singular",
            "replace_factor": 1,
            "replace_unit": "",
            "recipe_uuid": "",
            "barcode": "4002015511713",
        }
    )
