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

PLURAL_COLUMNS = PANTRY_COLUMNS + ["true_ingredient", "label"]
ALL_COLUMNS = PLURAL_COLUMNS + ["replace_factor", "replace_unit"]
PLURAL_ENDINGS = ["es", "n", "s", "ves"]
ALL_ENDINGS = [""] + PLURAL_ENDINGS


@pytest.fixture(scope="module")
def pantry_list_limit_init(gsheets_helper):
    with initialize(version_base=None, config_path="../../../config/"):
        config = compose(config_name="pantry_list")
        return PantryList(config.pantry_list, gsheets_helper)


class TestPantryList:
    @staticmethod
    def test__get_basic_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._get_basic_pantry_list()
        assert array_equal(
            df.label.unique(), ["basic_singular", "basic_plural"]
        )
        assert array_equal(df.replace_factor.unique(), [1])
        assert array_equal(df.replace_unit.unique(), [""])
        assert array_equal(sorted(df.plural_ending.unique()), ALL_ENDINGS)
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__get_replacement_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._get_replacement_pantry_list()
        assert array_equal(
            df.label.unique(),
            ["replacement_singular", "replacement_plural"],
        )
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__load_complex_pantry_list_for_search(pantry_list_limit_init):
        df = pantry_list_limit_init._load_complex_pantry_list_for_search()
        assert array_equal(
            sorted(df.label.unique()),
            [
                "bad_ingredient",
                "basic_plural",
                "basic_singular",
                "misspelled",
                "misspelled_replaced",
                "replacement_plural",
                "replacement_singular",
            ],
        )
        assert array_equal(sorted(df.plural_ending.unique()), ALL_ENDINGS)
        assert array_equal(df.columns, ALL_COLUMNS)
        assert df.ingredient.nunique() == df.shape[0]

    @staticmethod
    def test__retrieve_basic_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._retrieve_basic_pantry_list()
        assert array_equal(sorted(df.plural_ending.unique()), ALL_ENDINGS)
        assert array_equal(df.columns, PANTRY_COLUMNS)

    @staticmethod
    def test__retrieve_bad_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._retrieve_bad_pantry_list()
        assert array_equal(df.columns, ["ingredient", "plural_ending", "label"])

    @staticmethod
    def test__retrieve_misspelled_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._retrieve_misspelled_pantry_list()
        assert array_equal(
            sorted(df.label.unique()), ["misspelled", "misspelled_replaced"]
        )
        assert array_equal(df.columns, ALL_COLUMNS)

    @staticmethod
    def test__retrieve_replacement_pantry_list(pantry_list_limit_init):
        df = pantry_list_limit_init._retrieve_replacement_pantry_list()
        # subset of list
        assert array_equal(df.plural_ending.unique(), ["", "s", "es"])
        assert array_equal(
            df.columns,
            [
                "replacement_ingredient",
                "plural_ending",
                "replace_factor",
                "replace_unit",
                "true_ingredient",
                "item_plural",
            ],
        )
