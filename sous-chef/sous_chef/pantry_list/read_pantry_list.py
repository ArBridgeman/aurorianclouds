from dataclasses import dataclass

import pandas as pd
from omegaconf import DictConfig
from pandas import DataFrame
from sous_chef.abstract.search_dataframe import DataframeSearchable
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

FILE_LOGGER = get_logger(__name__)


@dataclass
class InnerJoinError(Exception):
    join_df: str
    old_shape: int
    new_shape: int
    message: str = "[inner join failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message}: mismatch of shapes of {self.join_df}, "
            f"before: {self.old_shape}, afterwards: {self.new_shape}."
        )


class PantryList(DataframeSearchable):
    def __init__(self, config: DictConfig, gsheets_helper: GsheetsHelper):
        super().__init__(config)
        self.workbook = gsheets_helper.get_workbook(self.config.workbook_name)
        self.basic_pantry_list = self._retrieve_basic_pantry_list()
        self.replacement_pantry_list = self._retrieve_replacement_pantry_list()
        self.dataframe = self._load_complex_pantry_list_for_search()

    @staticmethod
    def _check_join(df_name: str, shape_before: int, shape_new: int):
        if shape_new != shape_before:
            raise InnerJoinError(
                join_df=df_name,
                old_shape=shape_before,
                new_shape=shape_new,
            )

    def _get_basic_pantry_list(self):
        singular_list = self.basic_pantry_list.copy(deep=True)
        singular_list["true_ingredient"] = singular_list["ingredient"]
        singular_list["label"] = "basic_singular"

        mask_plural_items = singular_list["plural_ending"] != ""
        plural_list = singular_list[mask_plural_items].copy(deep=True)
        # create 'true_ingredient' to 'ingredient' for future aggregations
        plural_list["true_ingredient"] = plural_list["ingredient"]
        plural_list["ingredient"] = plural_list["item_plural"]
        plural_list["label"] = "basic_plural"

        basic_list = pd.concat([singular_list, plural_list], ignore_index=True)
        basic_list["replace_factor"] = 1
        basic_list["replace_unit"] = ""
        return basic_list

    @staticmethod
    def _get_pluralized_form(plural_ending: str, ingredient: str):
        if plural_ending in ["ies", "ves"]:
            return ingredient[:-1] + plural_ending
        else:
            return ingredient + plural_ending

    def _get_replacement_pantry_list(self):
        singular_list = self.replacement_pantry_list.copy(deep=True)
        singular_list["label"] = "replacement_singular"

        mask_plural_items = singular_list["plural_ending"] != ""
        plural_list = singular_list[mask_plural_items].copy(deep=True)
        plural_list["replacement_ingredient"] = plural_list["item_plural"]
        plural_list["label"] = "replacement_plural"

        replacement_list = pd.concat(
            [singular_list, plural_list], ignore_index=True
        )
        replacement_list = replacement_list[
            [
                "replacement_ingredient",
                "true_ingredient",
                "label",
                "replace_factor",
                "replace_unit",
            ]
        ]

        replacement_list = pd.merge(
            self.basic_pantry_list,
            replacement_list,
            left_on=["ingredient"],
            right_on=["true_ingredient"],
        )
        replacement_list["ingredient"] = replacement_list[
            "replacement_ingredient"
        ]
        return replacement_list.drop(columns=["replacement_ingredient"])

    def _load_complex_pantry_list_for_search(self):
        return pd.concat(
            [
                self._get_basic_pantry_list(),
                self._retrieve_bad_pantry_list(),
                self._retrieve_misspelled_pantry_list(),
                self._get_replacement_pantry_list(),
            ],
            ignore_index=True,
        )

    def _retrieve_basic_pantry_list(self) -> DataFrame:
        dataframe = self.workbook.get_worksheet(
            worksheet_name=self.config.ingredient_sheet_name,
            numerize=False,
        )
        dataframe["ingredient"] = dataframe.ingredient.str.strip()
        dataframe["item_plural"] = dataframe.apply(
            lambda x: self._get_pluralized_form(x.plural_ending, x.ingredient),
            axis=1,
        )
        return dataframe

    def _retrieve_bad_pantry_list(self) -> DataFrame:
        bad_list = self.workbook.get_worksheet(
            worksheet_name=self.config.bad_sheet_name,
            numerize=True,
        )[["ingredient"]]
        bad_list["plural_ending"] = ""
        bad_list["label"] = "bad_ingredient"
        return bad_list

    def _retrieve_misspelled_pantry_list(self) -> DataFrame:
        misspelled_list = self.workbook.get_worksheet(
            worksheet_name=self.config.misspelling_sheet_name,
            numerize=False,
        )

        mask_and_replaced = misspelled_list.replacement_ingredient != ""
        # set up misspelled ingredients that are not replaced
        without_replacement = misspelled_list[~mask_and_replaced][
            ["misspelled_ingredient", "true_ingredient"]
        ].copy()

        without_replacement["label"] = "misspelled"
        without_replacement["replace_factor"] = 1
        without_replacement["replace_unit"] = ""
        # set up misspelled ingredients that are replaced
        with_replacement = misspelled_list[mask_and_replaced].copy()
        with_replacement["label"] = "misspelled_replaced"

        shape_before = with_replacement.shape[0]
        with_replacement = pd.merge(
            self.replacement_pantry_list,
            with_replacement,
            how="outer",
            indicator=True,
            on=["replacement_ingredient", "true_ingredient"],
        )
        FILE_LOGGER.warning(
            with_replacement[with_replacement["_merge"] == "right_only"]
        )
        with_replacement = with_replacement[
            with_replacement["_merge"] == "both"
        ]
        self._check_join(
            "with_replacement", shape_before, with_replacement.shape[0]
        )

        with_replacement = with_replacement[
            [
                "misspelled_ingredient",
                "true_ingredient",
                "label",
                "replace_factor",
                "replace_unit",
            ]
        ]

        # join all misspelled ingredients with basic pantry list
        misspelled_list = pd.concat(
            [without_replacement, with_replacement], ignore_index=True
        )

        shape_before = misspelled_list.shape[0]
        misspelled_list = pd.merge(
            self.basic_pantry_list,
            misspelled_list,
            how="outer",
            indicator=True,
            left_on=["ingredient"],
            right_on=["true_ingredient"],
        )
        FILE_LOGGER.warning(
            misspelled_list[misspelled_list["_merge"] == "right_only"]
        )
        misspelled_list = misspelled_list[misspelled_list["_merge"] == "both"]
        self._check_join(
            "misspelled_list", shape_before, misspelled_list.shape[0]
        )

        # swap 'ingredient' to 'misspelled_ingredient' for search
        misspelled_list["ingredient"] = misspelled_list["misspelled_ingredient"]
        return misspelled_list.drop(columns=["misspelled_ingredient", "_merge"])

    def _retrieve_replacement_pantry_list(self) -> DataFrame:
        dataframe = self.workbook.get_worksheet(
            worksheet_name=self.config.replacement_sheet_name,
            numerize=True,
        )
        dataframe["item_plural"] = dataframe.apply(
            lambda x: self._get_pluralized_form(
                x.plural_ending, x.replacement_ingredient
            ),
            axis=1,
        )
        return dataframe
