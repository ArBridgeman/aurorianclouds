from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu._process_menu_recipe import MenuRecipeProcessor
from sous_chef.menu.create_menu.exceptions import MenuIncompleteError
from sous_chef.menu.create_menu.models import (
    LoadedMenuSchema,
    TmpMenuSchema,
    TypeProcessOrder,
    validate_menu_schema,
)
from structlog import get_logger
from termcolor import cprint

FILE_LOGGER = get_logger(__name__)


class MenuTemplateFiller(BaseWithExceptionHandling):
    def __init__(
        self,
        menu_config: DictConfig,
        ingredient_formatter: IngredientFormatter,
        menu_recipe_processor: MenuRecipeProcessor,
    ):
        self.menu_config = menu_config
        self.ingredient_formatter = ingredient_formatter
        self.menu_recipe_processor = menu_recipe_processor

    def fill_menu_template(
        self, menu_template_df: DataFrameBase[LoadedMenuSchema]
    ) -> DataFrameBase[TmpMenuSchema]:
        self.record_exception = []

        tmp_menu_template_df = self._get_ordered_menu_template(menu_template_df)

        final_menu_df = pd.DataFrame()
        processed_uuid_list = []
        for _, row in tmp_menu_template_df.iterrows():
            processed_entry = self._process_menu(
                row=row,
                processed_uuid_list=processed_uuid_list,
            )

            # in cases where error is logged
            if processed_entry is None:
                continue

            if processed_entry["type"] == "recipe":
                processed_uuid_list.append(processed_entry.uuid)

            processed_df = pd.DataFrame([processed_entry])
            final_menu_df = pd.concat([processed_df, final_menu_df])

        if len(self.record_exception) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message="will not send to finalize until fixed"
            )

        final_menu_df.uuid = final_menu_df.uuid.replace(np.nan, "NaN")
        return validate_menu_schema(
            dataframe=final_menu_df.sort_values(
                by=["cook_datetime"], ignore_index=True
            ),
            model=TmpMenuSchema,
        )

    @staticmethod
    def _get_ordered_menu_template(
        menu_template_df: DataFrameBase[LoadedMenuSchema],
    ) -> DataFrameBase[LoadedMenuSchema]:
        menu_template_df = menu_template_df.copy(deep=True)

        # sort by desired order to be processed
        menu_template_df["process_order"] = menu_template_df["type"].apply(
            lambda x: TypeProcessOrder[x].value
        )
        menu_template_df["is_unrated"] = (
            menu_template_df.selection == "unrated"
        ).astype(int)

        return menu_template_df.sort_values(
            by=["is_unrated", "process_order"], ascending=[False, True]
        ).drop(columns=["process_order", "is_unrated"])

    def _process_menu(
        self,
        row: pd.Series,
        processed_uuid_list: List,
    ) -> DataFrameBase[TmpMenuSchema]:
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        tmp_row = row.copy(deep=True)

        if tmp_row["type"] == "ingredient":
            return self._process_ingredient(tmp_row)
        if tmp_row["type"] in ["category", "tag", "filter"]:
            return self.menu_recipe_processor.select_random_recipe(
                row=tmp_row,
                entry_type=tmp_row["type"],
                processed_uuid_list=processed_uuid_list,
            )
        return self.menu_recipe_processor.retrieve_recipe(tmp_row,
                                                          processed_uuid_list=processed_uuid_list,)

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _process_ingredient(
        self, row: pd.Series
    ) -> DataFrameBase[TmpMenuSchema]:
        # do NOT need returned, as just ensuring exists
        self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

        row["time_total"] = timedelta(
            minutes=int(self.menu_config.ingredient.default_cook_minutes)
        )
        row["rating"] = np.NaN
        row["uuid"] = np.NaN
        row["cook_datetime"] = row["cook_datetime"] - row["time_total"]
        row["prep_datetime"] = row["cook_datetime"]
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)
