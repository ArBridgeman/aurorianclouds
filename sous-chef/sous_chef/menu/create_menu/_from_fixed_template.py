from datetime import timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.menu.create_menu._menu_basic import MenuBasic
from sous_chef.menu.create_menu._select_menu_template import MenuTemplates
from sous_chef.menu.create_menu.exceptions import MenuIncompleteError
from sous_chef.menu.create_menu.models import (
    AllMenuSchema,
    TmpMenuSchema,
    TypeProcessOrder,
    validate_menu_schema,
)
from structlog import get_logger
from termcolor import cprint

FILE_LOGGER = get_logger(__name__)


class MenuFromFixedTemplate(MenuBasic):
    def finalize_fixed_menu(self) -> DataFrameBase[TmpMenuSchema]:
        self.record_exception = []

        fixed_templates = MenuTemplates(
            config=self.menu_config.fixed,
            due_date_formatter=self.due_date_formatter,
            gsheets_helper=self.gsheets_helper,
        )
        self.dataframe = fixed_templates.load_template_menu()

        # sort by desired order to be processed
        self.dataframe["process_order"] = self.dataframe["type"].apply(
            lambda x: TypeProcessOrder[x].value
        )
        self.dataframe["is_unrated"] = (
            self.dataframe.selection == "unrated"
        ).astype(int)

        self.dataframe = self.dataframe.sort_values(
            by=["is_unrated", "process_order"], ascending=[False, True]
        ).drop(columns=["process_order", "is_unrated"])

        future_uuid_tuple = ()
        if self.menu_config.fixed.already_in_future_menus.active:
            future_uuid_tuple = self._get_future_menu_uuids(
                future_menus=fixed_templates.select_upcoming_menus(
                    num_weeks_in_future=self.menu_config.fixed.already_in_future_menus.num_weeks  # noqa: E501
                )
            )

        holder_dataframe = pd.DataFrame()
        processed_uuid_list = []
        for _, entry in self.dataframe.iterrows():
            processed_entry = self._process_menu(
                row=entry,
                processed_uuid_list=processed_uuid_list,
                future_uuid_tuple=future_uuid_tuple,
            )

            # in cases where error is logged
            if processed_entry is None:
                continue

            if processed_entry["type"] == "recipe":
                processed_uuid_list.append(processed_entry.uuid)

            processed_df = pd.DataFrame([processed_entry])
            holder_dataframe = pd.concat([processed_df, holder_dataframe])
        self.dataframe = holder_dataframe

        if len(self.record_exception) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message="will not send to finalize until fixed"
            )

        self.dataframe = self.dataframe.sort_values(
            by=["cook_datetime"], ignore_index=True
        )
        self.dataframe.uuid = self.dataframe.uuid.replace(np.nan, "NaN")
        return validate_menu_schema(
            dataframe=self.dataframe, model=TmpMenuSchema
        )

    def _get_future_menu_uuids(
        self, future_menus: DataFrameBase[AllMenuSchema]
    ) -> Tuple:
        FILE_LOGGER.info("[_get_future_menu_uuids]")
        mask_type = future_menus["type"] == "recipe"
        return tuple(
            self.recipe_book.get_recipe_by_title(recipe).uuid
            for recipe in future_menus[mask_type]["item"].values
        )

    def _process_menu(
        self,
        row: pd.Series,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple] = (),
    ) -> DataFrameBase[TmpMenuSchema]:
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        tmp_row = row.copy(deep=True)
        if row["type"] == "ingredient":
            return self._process_ingredient(tmp_row)
        return self._process_menu_recipe(
            tmp_row,
            processed_uuid_list=processed_uuid_list,
            future_uuid_tuple=future_uuid_tuple,
        )

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

    def _process_menu_recipe(
        self,
        row: pd.Series,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple] = (),
    ) -> DataFrameBase[TmpMenuSchema]:
        if row["type"] in ["category", "tag", "filter"]:
            return self._select_random_recipe(
                row=row,
                entry_type=row["type"],
                processed_uuid_list=processed_uuid_list,
                future_uuid_tuple=future_uuid_tuple,
            )
        return self._retrieve_recipe(
            row,
            processed_uuid_list=processed_uuid_list,
            future_uuid_tuple=future_uuid_tuple,
        )
