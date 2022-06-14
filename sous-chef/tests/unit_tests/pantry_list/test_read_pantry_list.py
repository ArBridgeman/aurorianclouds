from unittest.mock import patch

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
        assert (
            pantry_list._get_pluralized_form(plural_ending, ingredient)
            == expected_result
        )
