import pandas as pd
from omegaconf import DictConfig
from pandas import DataFrame, Series
from sous_chef.abstract.search_dataframe import DataframeSearchable
from sous_chef.messaging.gsheets_api import GsheetsHelper
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


class PantryList(DataframeSearchable):
    def __init__(self, config: DictConfig, gsheets_helper: GsheetsHelper):
        super().__init__(config)
        self.gsheets_helper = gsheets_helper
        self.basic_pantry_list = self._retrieve_basic_pantry_list()
        self.dataframe = self._load_complex_pantry_list_for_search()

    @staticmethod
    def _get_pluralized_form(row: Series):
        if row.plural_ending in ["ies", "ves"]:
            return row.ingredient[:-1] + row.plural_ending
        else:
            return row.ingredient + row.plural_ending

    def _load_complex_pantry_list_for_search(self):
        misspelled_pantry_list = self._retrieve_misspelled_pantry_list()
        plural_pantry_list = self._retrieve_plural_pantry_list()
        self.basic_pantry_list["true_ingredient"] = self.basic_pantry_list[
            "ingredient"
        ]
        return pd.concat(
            [self.basic_pantry_list, misspelled_pantry_list, plural_pantry_list]
        )

    def _retrieve_basic_pantry_list(self) -> DataFrame:
        dataframe = self.gsheets_helper.get_sheet_as_df(
            self.config.workbook_name, self.config.ingredient_sheet_name
        )
        dataframe["item_plural"] = dataframe.apply(
            self._get_pluralized_form, axis=1
        )
        return dataframe

    def _retrieve_misspelled_pantry_list(self) -> DataFrame:
        misspelled_pantry_list = self.gsheets_helper.get_sheet_as_df(
            self.config.workbook_name, self.config.misspelling_sheet_name
        )

        misspelled_pantry_list = pd.merge(
            self.basic_pantry_list,
            misspelled_pantry_list,
            how="inner",
            left_on="ingredient",
            right_on="true_ingredient",
        )
        # swap 'ingredient' to 'misspelled_ingredient' for search
        misspelled_pantry_list["ingredient"] = misspelled_pantry_list[
            "misspelled_ingredient"
        ]
        return misspelled_pantry_list

    def _retrieve_plural_pantry_list(self) -> DataFrame:
        # TODO want gsheets to convert '' to NAs or simple function?
        # otherwise, we have to make sure to do this & not isna
        mask_plural_items = self.basic_pantry_list["plural_ending"] != ""
        plural_pantry_list = self.basic_pantry_list[mask_plural_items].copy(
            deep=True
        )

        # create 'true_ingredient' to 'plural_form' for search
        plural_pantry_list["true_ingredient"] = plural_pantry_list["ingredient"]
        # swap 'ingredient' to 'item_plural' for search
        plural_pantry_list["ingredient"] = plural_pantry_list["item_plural"]
        return plural_pantry_list
