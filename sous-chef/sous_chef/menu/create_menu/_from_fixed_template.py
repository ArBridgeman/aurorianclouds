from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
from sous_chef.abstract.extended_enum import ExtendedIntEnum
from sous_chef.menu.create_menu._menu_basic import (
    MenuBasic,
    MenuIncompleteError,
)
from structlog import get_logger
from termcolor import cprint

FILE_LOGGER = get_logger(__name__)


class TypeProcessOrder(ExtendedIntEnum):
    recipe = 0
    ingredient = 1
    filter = 2
    tag = 3
    category = 4


class MenuFromFixedTemplate(MenuBasic):
    def finalize_fixed_menu(self):
        default_prep_time = self.config.prep_separate.default_time

        def _get_default_prep_datetime(row: pd.Series):
            return self.due_date_formatter.replace_time_with_meal_time(
                due_date=row.eat_datetime - timedelta(days=int(row.prep_day)),
                meal_time=default_prep_time,
            )

        self.record_exception = []

        self.dataframe = self._load_fixed_menu().reset_index(drop=True)

        # remove menu entries that are inactive and drop column
        mask_inactive = self.dataframe.inactive.str.upper() == "Y"
        self.dataframe = self.dataframe.loc[~mask_inactive].drop(
            columns=["inactive"]
        )
        self.dataframe.selection.replace("", np.NaN, inplace=True)
        # applied schema model coerces int already
        self.dataframe.freeze_factor.replace("", "0", inplace=True)
        self.dataframe.prep_day.replace("", "0", inplace=True)
        self.dataframe.defrost = self.dataframe.defrost.replace(
            "", "N"
        ).str.upper()
        if "override_check" in self.dataframe.columns:
            self.dataframe.override_check = (
                self.dataframe.override_check.fillna("")
                .replace("", "N")
                .str.upper()
            )
        else:
            self.dataframe["override_check"] = "N"

        self.dataframe["eat_datetime"] = self.dataframe.apply(
            lambda row: self.due_date_formatter.get_due_datetime_with_meal_time(
                weekday=row.weekday, meal_time=row.meal_time
            ),
            axis=1,
        )
        self.dataframe["prep_datetime"] = self.dataframe.apply(
            _get_default_prep_datetime, axis=1
        )

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
        # validate schema & process menu
        self._validate_menu_schema()

        holder_dataframe = pd.DataFrame()
        processed_uuid_list = []
        for _, entry in self.dataframe.iterrows():
            processed_entry = self._process_menu(
                entry.copy(deep=True), processed_uuid_list=processed_uuid_list
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

        self.dataframe.drop(
            columns=["eat_datetime", "override_check", "prep_day"],
            inplace=True,
        )
        self._save_menu()

    @staticmethod
    def _check_fixed_menu_number(menu_number: int):
        if menu_number is None:
            raise ValueError("fixed menu number not specified")
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")

    def _load_fixed_menu(self):
        menu_file = self.config.fixed.workbook

        sheet_to_mealtime = {
            "breakfast": "breakfast",
            "snack": "snack",
            "dinner": "dinner",
            "dessert": "dessert",
        }

        combined_menu = pd.DataFrame()
        for sheet, meal_time in sheet_to_mealtime.items():
            sheet_pd = self.gsheets_helper.get_worksheet(
                menu_file, worksheet_name=sheet
            )
            sheet_pd["meal_time"] = meal_time
            combined_menu = pd.concat([combined_menu, sheet_pd])

        basic_number = self.config.fixed.basic_number
        # self._check_fixed_menu_number(basic_number)

        menu_number = self.config.fixed.menu_number
        self._check_fixed_menu_number(menu_number)

        combined_menu = combined_menu[
            combined_menu.menu.astype(int).isin([basic_number, menu_number])
        ]

        combined_menu["weekday"] = (
            combined_menu.day.str.split("_")
            .str[1]
            .apply(self._get_weekday_from_short)
        )

        combined_menu.drop(columns=["day", "menu", "who"], inplace=True)
        combined_menu = combined_menu.sort_values(by=["weekday", "meal_time"])

        # TODO create test for
        mask_skip_none = combined_menu["weekday"].isna()
        if sum(mask_skip_none) > 0:
            FILE_LOGGER.warning(
                "Menu entries ignored",
                skipped_entries=combined_menu[mask_skip_none],
            )
        return combined_menu[~mask_skip_none]

    def _process_menu(self, row: pd.Series, processed_uuid_list: List):
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        if row["type"] == "ingredient":
            return self._process_ingredient(row)
        return self._process_menu_recipe(
            row, processed_uuid_list=processed_uuid_list
        )

    def _process_ingredient(self, row: pd.Series):
        # do NOT need returned, as just ensuring exists
        self._check_manual_ingredient(row=row)

        row["time_total"] = timedelta(
            minutes=int(self.config.ingredient.default_cook_minutes)
        )

        cook_datetime = row["eat_datetime"] - row["time_total"]
        row["cook_datetime"] = cook_datetime
        row["prep_datetime"] = cook_datetime
        return row

    def _process_menu_recipe(self, row: pd.Series, processed_uuid_list: List):
        if row["type"] in ["category", "tag", "filter"]:
            return self._select_random_recipe(
                row=row,
                entry_type=row["type"],
                processed_uuid_list=processed_uuid_list,
            )

        return self._retrieve_recipe(
            row, processed_uuid_list=processed_uuid_list
        )
