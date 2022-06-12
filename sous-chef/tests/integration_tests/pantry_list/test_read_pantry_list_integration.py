from unittest.mock import patch

import pytest
from hydra import compose, initialize
from numpy import array_equal
from sous_chef.pantry_list.read_pantry_list import PantryList

PANTRY_COLUMNS = [
    "ingredient",
    "plural_ending",
    "is_staple",
    "group",
    "store",
    "recipe_uuid",
    "barcode",
    "item_plural",
]

# TODO need to add factor here where 1 default
ALL_COLUMNS = PANTRY_COLUMNS + ["true_ingredient", "label"]
PLURAL_ENDINGS = ["es", "n", "s", "ves"]
ALL_ENDINGS = PLURAL_ENDINGS + [""]


@pytest.fixture(scope="module")
def pantry_list(gsheets_helper):
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="pantry_list")
    return PantryList(config.pantry_list, gsheets_helper)


@pytest.fixture(scope="module")
def pantry_list_limit_init(gsheets_helper):
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="pantry_list")
        with patch.object(PantryList, "__post_init__", return_value=None):
            return PantryList(config.pantry_list, gsheets_helper)


class TestPantryList:
    @staticmethod
    def test__get_basic_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._get_basic_pantry_list()
        assert array_equal(df.label.unique(), ["basic_form"])
        assert array_equal(df.plural_ending.unique(), ALL_ENDINGS)
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__load_complex_pantry_list_for_search(pantry_list_limit_init):
        df = pantry_list_limit_init._load_complex_pantry_list_for_search()
        assert array_equal(
            df.label.unique(), ["basic_form", "misspelled_form", "plural_form"]
        )
        assert array_equal(df.plural_ending.unique(), ALL_ENDINGS)
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__retrieve_basic_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._retrieve_basic_pantry_list()
        assert array_equal(df.plural_ending.unique(), ALL_ENDINGS)
        assert array_equal(df.columns, PANTRY_COLUMNS)

    @staticmethod
    def test__retrieve_misspelled_pantry_list(pantry_list):
        # TODO need to modify/connect with replacement list
        df = pantry_list._retrieve_misspelled_pantry_list()
        assert array_equal(df.label.unique(), ["misspelled_form"])
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__retrieve_plural_pantry_list(pantry_list):
        df = pantry_list._retrieve_plural_pantry_list()
        assert array_equal(df.label.unique(), ["plural_form"])
        assert array_equal(df.ingredient.values, df.item_plural.values)
        assert array_equal(df.plural_ending.unique(), PLURAL_ENDINGS)
        assert array_equal(df.columns, ALL_COLUMNS)
