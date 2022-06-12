from unittest.mock import patch

import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.pantry_list.read_pantry_list import PantryList


@pytest.fixture
def pantry_list():
    with initialize(version_base=None, config_path="../../../config"):
        config = compose(config_name="pantry_list")
        with patch.object(PantryList, "__init__", lambda x, y, z: None):
            return PantryList(config, None)


class TestPantryList:
    @staticmethod
    @pytest.mark.parametrize(
        "ingredient,plural_ending,expected_result",
        [
            ("orange", "s", "oranges"),
            ("squash", "es", "squashes"),
            ("leaf", "ves", "leaves"),
            ("berry", "ies", "berries"),
            ("bratkartoffel", "n", "bratkartoffeln"),
        ],
    )
    def test__get_pluralized_form(
        pantry_list, ingredient, plural_ending, expected_result
    ):
        row = pd.DataFrame(
            {"plural_ending": plural_ending, "ingredient": ingredient},
            index=[0],
        ).squeeze()
        assert pantry_list._get_pluralized_form(row) == expected_result
