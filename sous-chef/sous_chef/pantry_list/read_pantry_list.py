import pandas as pd
from omegaconf import DictConfig
from pandas import DataFrame, Series
from sous_chef.abstract.search_dataframe import DataframeSearchable
from sous_chef.messaging.gsheets_api import GsheetsHelper
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)

SELECT_BASIC_LIST_COLUMNS = [
    "ingredient",
    "plural_ending",
    "is_staple",
    "group",
    "store",
    "recipe_uuid",
    "barcode",
    "item_plural",
    "true_ingredient",
]


class PantryList(DataframeSearchable):
    def __init__(self, config: DictConfig, gsheets_helper: GsheetsHelper):
        super().__init__(config)
        self.gsheets_helper = gsheets_helper
        self.basic_pantry_list = self._retrieve_basic_pantry_list()

    def __post_init__(self):
        self.dataframe = self._load_complex_pantry_list_for_search()

    def _get_basic_pantry_list(self):
        basic_list = self.basic_pantry_list.copy(deep=True)
        basic_list["true_ingredient"] = basic_list["ingredient"]
        basic_list["label"] = "basic_form"
        return basic_list

    @staticmethod
    def _get_pluralized_form(row: Series):
        if row.plural_ending in ["ies", "ves"]:
            return row.ingredient[:-1] + row.plural_ending
        else:
            return row.ingredient + row.plural_ending

    def _load_complex_pantry_list_for_search(self):
        basic_pantry_list = self._get_basic_pantry_list()
        misspelled_pantry_list = self._retrieve_misspelled_pantry_list()
        plural_pantry_list = self._retrieve_plural_pantry_list()
        return pd.concat(
            [basic_pantry_list, misspelled_pantry_list, plural_pantry_list]
        )

    def _retrieve_basic_pantry_list(self) -> DataFrame:
        dataframe = self.gsheets_helper.get_worksheet(
            self.config.workbook_name, self.config.ingredient_sheet_name
        )
        dataframe["item_plural"] = dataframe.apply(
            self._get_pluralized_form, axis=1
        )
        return dataframe

    def _retrieve_misspelled_pantry_list(self) -> DataFrame:
        misspelled_list = self.gsheets_helper.get_worksheet(
            self.config.workbook_name, self.config.misspelling_sheet_name
        )
        misspelled_list["label"] = "misspelled_form"

        misspelled_list = pd.merge(
            self.basic_pantry_list,
            misspelled_list,
            how="inner",
            left_on=["ingredient"],
            right_on=["true_ingredient"],
        )
        # swap 'ingredient' to 'misspelled_ingredient' for search
        misspelled_list["ingredient"] = misspelled_list["misspelled_ingredient"]
        return misspelled_list.drop(
            columns=["misspelled_ingredient", "replacement_ingredient"]
        )

    def _retrieve_plural_pantry_list(self) -> DataFrame:
        # TODO want gsheets to convert '' to NAs or simple function?
        # otherwise, we have to make sure to do this & not isna
        mask_plural_items = self.basic_pantry_list["plural_ending"] != ""
        plural_list = self.basic_pantry_list[mask_plural_items].copy(deep=True)

        # create 'true_ingredient' to 'plural_form' for search
        plural_list["true_ingredient"] = plural_list["ingredient"]
        # swap 'ingredient' to 'item_plural' for search
        plural_list["ingredient"] = plural_list["item_plural"]
        plural_list["label"] = "plural_form"
        return plural_list
