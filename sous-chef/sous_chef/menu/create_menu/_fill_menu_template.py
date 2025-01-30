from datetime import timedelta

import numpy as np
import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.ingredient.format_ingredient import (
    IngredientFormatter,
    MapIngredientErrorToException,
)
from sous_chef.formatter.ingredient.format_line_abstract import (
    MapLineErrorToException,
)
from sous_chef.menu.create_menu._process_menu_recipe import MenuRecipeProcessor
from sous_chef.menu.create_menu.exceptions import (
    MenuFutureError,
    MenuIncompleteError,
    MenuQualityError,
)
from sous_chef.menu.create_menu.models import (
    LoadedMenuSchema,
    RandomSelectType,
    TmpMenuSchema,
    TypeProcessOrder,
    validate_menu_schema,
)
from sous_chef.menu.record_menu_history import MapMenuHistoryErrorToException
from sous_chef.recipe_book.recipe_util import MapRecipeErrorToException
from structlog import get_logger
from termcolor import cprint

from utilities.extended_enum import ExtendedEnum, extend_enum

FILE_LOGGER = get_logger(__name__)


@extend_enum(
    [
        MapMenuHistoryErrorToException,
        MapIngredientErrorToException,
        MapLineErrorToException,
        MapRecipeErrorToException,
    ]
)
class MapMenuErrorToException(ExtendedEnum):
    menu_quality_check = MenuQualityError
    menu_future_error = MenuFutureError


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

        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.menu_config.errors,
            exception_mapper=MapMenuErrorToException,
        )

    def fill_menu_template(
        self, menu_template_df: DataFrameBase[LoadedMenuSchema]
    ) -> DataFrameBase[TmpMenuSchema]:
        self.record_exception = []

        tmp_menu_template_df = self._get_ordered_menu_template(menu_template_df)

        final_menu_df = pd.DataFrame()
        for _, row in tmp_menu_template_df.iterrows():
            processed_df = self._process_menu(row=row)

            # in cases where error is logged
            if processed_df is None:
                continue

            final_menu_df = pd.concat([processed_df, final_menu_df])

        if (num_errors := len(self.record_exception)) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message=f"{num_errors} menu errors to resolve"
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
            menu_template_df.selection == RandomSelectType.unrated.value
        ).astype(int)

        return menu_template_df.sort_values(
            by=["is_unrated", "process_order"], ascending=[False, True]
        ).drop(columns=["process_order", "is_unrated"])

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _process_menu(
        self,
        row: pd.Series,
    ) -> DataFrameBase[TmpMenuSchema]:
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        tmp_row = row.copy(deep=True)

        if tmp_row["type"] == TypeProcessOrder.ingredient.name:
            return self._process_ingredient(tmp_row)
        if tmp_row["type"] in [
            TypeProcessOrder.category.name,
            TypeProcessOrder.filter.name,
            TypeProcessOrder.tag.name,
        ]:
            return self.menu_recipe_processor.select_random_recipe(
                row=tmp_row,
                entry_type=tmp_row["type"],
            )
        return self.menu_recipe_processor.retrieve_recipe(tmp_row)

    def _process_ingredient(
        self, row: pd.Series
    ) -> DataFrameBase[TmpMenuSchema]:
        # do NOT need returned, as just ensuring exists
        self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

        entry_df = pd.DataFrame(
            [
                {
                    **row.to_dict(),
                    "time_total": timedelta(
                        minutes=int(
                            self.menu_config.ingredient.default_cook_minutes
                        )
                    ),
                    "rating": np.NaN,
                    "uuid": np.NaN,
                }
            ]
        )
        entry_df["cook_datetime"] = (
            entry_df["cook_datetime"] - entry_df["time_total"]
        )
        entry_df["prep_datetime"] = entry_df["cook_datetime"]
        return validate_menu_schema(dataframe=entry_df, model=TmpMenuSchema)
