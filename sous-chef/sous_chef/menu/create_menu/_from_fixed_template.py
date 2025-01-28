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
    def fill_menu_template(self) -> DataFrameBase[TmpMenuSchema]:
        self.record_exception = []

        fixed_templates = MenuTemplates(
            config=self.menu_config.fixed,
            due_date_formatter=self.due_date_formatter,
            gsheets_helper=self.gsheets_helper,
        )
        menu_template_df = fixed_templates.load_template_menu()

        # sort by desired order to be processed
        menu_template_df["process_order"] = menu_template_df["type"].apply(
            lambda x: TypeProcessOrder[x].value
        )
        menu_template_df["is_unrated"] = (
            menu_template_df.selection == "unrated"
        ).astype(int)

        menu_template_df = menu_template_df.sort_values(
            by=["is_unrated", "process_order"], ascending=[False, True]
        ).drop(columns=["process_order", "is_unrated"])

        future_uuid_tuple = ()
        if self.menu_config.fixed.already_in_future_menus.active:
            future_uuid_tuple = self._get_future_menu_uuids(
                future_menus=fixed_templates.select_upcoming_menus(
                    num_weeks_in_future=self.menu_config.fixed.already_in_future_menus.num_weeks  # noqa: E501
                )
            )

        final_menu_df = pd.DataFrame()
        processed_uuid_list = []
        for _, entry in menu_template_df.iterrows():
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
