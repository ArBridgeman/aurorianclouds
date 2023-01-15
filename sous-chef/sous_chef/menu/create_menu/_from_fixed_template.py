from datetime import timedelta
from typing import List

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
    tag = 2
    category = 3


class MenuFromFixedTemplate(MenuBasic):
    def finalize_fixed_menu(self):
        self.record_exception = []

        self.dataframe = self._load_fixed_menu().reset_index(drop=True)

        # remove menu entries that are inactive and drop column
        mask_inactive = self.dataframe.inactive.str.upper() == "Y"
        self.dataframe = self.dataframe.loc[~mask_inactive].drop(
            columns=["inactive"]
        )

        # applied schema model coerces int already
        self.dataframe.freeze_factor.replace("", "0", inplace=True)
        self.dataframe.prep_day_before.replace("", "0", inplace=True)
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

        # sort by desired order to be processed
        self.dataframe["process_order"] = self.dataframe["type"].apply(
            lambda x: TypeProcessOrder[x].value
        )
        self.dataframe = self.dataframe.sort_values(
            by=["process_order"], ascending=True
        ).drop(columns=["process_order"])
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
            columns=["eat_datetime", "override_check", "prep_day_before"],
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
        menu_basic_file = self.config.fixed.basic
        menu_basic = self.gsheets_helper.get_worksheet(
            menu_basic_file, menu_basic_file
        )

        menu_number = self.config.fixed.menu_number
        self._check_fixed_menu_number(menu_number)
        menu_fixed_file = f"{self.config.fixed.file_prefix}{menu_number}"
        menu_fixed = self.gsheets_helper.get_worksheet(
            menu_fixed_file, menu_fixed_file
        )

        combined_menu = pd.concat([menu_basic, menu_fixed]).sort_values(
            by=["weekday", "meal_time"]
        )
        combined_menu["weekday"] = combined_menu.weekday.apply(
            self._get_cook_day_as_weekday
        )

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
        if row["type"] in ["category", "tag"]:
            method = "get_random_recipe_by_category"
            if row["type"] == "tag":
                method = "get_random_recipe_by_tag"
            return self._select_random_recipe(
                row=row, method=method, processed_uuid_list=processed_uuid_list
            )

        return self._retrieve_recipe(
            row, processed_uuid_list=processed_uuid_list
        )