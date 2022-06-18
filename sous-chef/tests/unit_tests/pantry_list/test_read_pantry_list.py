from unittest.mock import patch

import pytest
from hydra import compose, initialize
from sous_chef.pantry_list.read_pantry_list import InnerJoinError, PantryList


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

    @staticmethod
    @pytest.mark.parametrize(
        "df_name,old_shape,new_shape",
        [
            ("test_df", 1, 3),
            ("test_df", 11, 10),
        ],
    )
    def test__check_join__raises_error_when_shape_mismatch(
        pantry_list, df_name, old_shape, new_shape
    ):
        with pytest.raises(InnerJoinError) as error:
            pantry_list._check_join(df_name, old_shape, new_shape)
        assert (
            str(error.value)
            == f"[inner join failed]: mismatch of shapes of {df_name}, "
            f"before: {old_shape}, afterwards: {new_shape}."
        )

    @staticmethod
    @pytest.mark.parametrize(
        "df_name,old_shape,new_shape",
        [
            ("test_df", 10, 10),
        ],
    )
    def test__check_join__passes_when_shape_match(
        pantry_list, df_name, old_shape, new_shape
    ):
        pantry_list._check_join(df_name, old_shape, new_shape)
