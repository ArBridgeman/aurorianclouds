import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sous_chef.abstract.search_dataframe import (
    DataframeSearchable,
    DirectSearchError,
)
from structlog import get_logger

HOME_PATH = str(Path.home())
FILE_LOGGER = get_logger(__name__)

INP_JSON_COLUMNS = {
    "title": str,
    "preparationTime": str,
    "cookingTime": str,
    "totalTime": str,
    "ingredients": str,
    "instructions": str,
    "rating": float,
    "favorite": bool,
    "categories": list,
    # TODO quantity should be split/standardized...it's bad!!!
    "quantity": str,
    "tags": list,
    "uuid": str,
}


class SelectRandomRecipeError(DirectSearchError):
    message = "[select random recipe failed]"


@dataclass
class Recipe:
    title: str
    rating: float
    total_cook_time: datetime
    ingredient_field: str
    factor: float = 1.0


@dataclass
class RecipeBook(DataframeSearchable):
    def __post_init__(self):
        # load basic recipe book to self.dataframe
        self.dataframe = self._read_recipe_book()
        if self.config.deduplicate:
            self._select_highest_rated_when_duplicated_name()

    def get_random_recipe_by_category(self, category: str) -> Recipe:
        return self._select_random_recipe_weighted_by_rating(
            method_match=self._is_value_in_list,
            field="categories",
            search_term=category,
        )

    def get_random_recipe_by_tag(self, tag: str) -> Recipe:
        return self._select_random_recipe_weighted_by_rating(
            method_match=self._is_value_in_list, field="tags", search_term=tag
        )

    def get_recipe_by_title(self, title) -> Recipe:
        result = self.retrieve_match(field="title", search_term=title)
        return Recipe(
            title=result.title,
            rating=result.rating,
            ingredient_field=result.ingredients,
            total_cook_time=result.totalTime,
        )

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        # TODO would be better if columns handled upon import to casefold
        return search_term.casefold() in [entry.casefold() for entry in row]

    def _read_recipe_book(self):
        recipe_book_path = Path(HOME_PATH, self.config.path)
        return pd.concat(
            [
                retrieve_format_recipe_df(recipe_file)
                for recipe_file in recipe_book_path.glob(
                    self.config.file_pattern
                )
            ]
        )

    def _select_random_recipe_weighted_by_rating(
        self, method_match: Callable, field: str, search_term: str
    ):
        config_random = self.config.random_select
        mask_selection = self.dataframe[field].apply(
            lambda row: method_match(row, search_term)
        )
        # TODO CODE-167 need way to remove recent entries per history log
        if (count := sum(mask_selection)) > config_random.min_thresh_error:
            if count < config_random.min_thresh_warning:
                FILE_LOGGER.warning(
                    "[select random recipe]",
                    selection=f"{field}={search_term}",
                    warning=f"only {count} entries available",
                    thresh=config_random.min_thresh_warning,
                )

            result_df = self.dataframe[mask_selection]
            weighting = result_df.rating.copy(deep=True).replace(
                0, config_random.default_rating
            )
            result = result_df.sample(n=1, weights=weighting).iloc[0]
            return Recipe(
                title=result.title,
                rating=result.rating,
                ingredient_field=result.ingredients,
                total_cook_time=result.totalTime,
            )
        raise SelectRandomRecipeError(field=field, search_term=search_term)

    def _select_highest_rated_when_duplicated_name(self):
        self.dataframe = self.dataframe.sort_values(["rating"], ascending=False)
        self.dataframe = self.dataframe.drop_duplicates(["title"], keep="first")


def flatten_dict_to_list(row_entry):
    values = []
    if row_entry is not np.nan and row_entry is not None:
        for entry in row_entry:
            values.extend(entry.values())
    return values


def create_timedelta(row_entry):
    from fractions import Fraction

    row_entry = row_entry.lower().strip()
    if row_entry.isdecimal():
        return pd.to_timedelta(int(row_entry), unit="minutes")
    else:
        # has units in string or is nan
        # cleaning, then parsing with pd.to_timedelta
        row_entry = re.sub("time", "", row_entry)
        row_entry = re.sub("prep", "", row_entry)
        row_entry = re.sub("cooking", "", row_entry)
        row_entry = re.sub("minut[eo]s.?", "min", row_entry)
        row_entry = re.sub(r"^[\D]+", "", row_entry)
        row_entry = re.sub(r"mins\.?$", "min", row_entry)
        if re.match(r"^\d{1,2}:\d{1,2}$", row_entry):
            row_entry = "{}:00".format(row_entry)

        # handle fractions properly
        # todo outsource to separate clean function
        if "/" in row_entry:
            groups = re.match(
                r"^(\d?\s\d+[\.\,\/]?\d*)?\s([\s\-\_\w\%]+)", row_entry
            )
            if groups:
                float_conv = float(
                    sum(Fraction(s) for s in groups.group(1).split())
                )
                row_entry = f"{float_conv} {groups.group(2).strip()}"

        # errors = "ignore", if confident we want to ignore further issues
        return pd.to_timedelta(row_entry, unit=None, errors="raise")


# TODO separate active vs inactive cooking; make resilient to problems
def retrieve_format_recipe_df(
    json_file, cols_to_select=INP_JSON_COLUMNS.keys()
):
    tmp_df = pd.read_json(json_file, dtype=INP_JSON_COLUMNS)
    for col in cols_to_select:
        if col not in tmp_df.columns:
            tmp_df[col] = None
    tmp_df = tmp_df[cols_to_select]
    tmp_df["totalTime"] = tmp_df["totalTime"].apply(create_timedelta)
    tmp_df["preparationTime"] = tmp_df["preparationTime"].apply(
        create_timedelta
    )
    tmp_df["cookingTime"] = tmp_df["cookingTime"].apply(create_timedelta)
    tmp_df["categories"] = tmp_df.categories.apply(flatten_dict_to_list)
    tmp_df["tags"] = tmp_df.tags.apply(flatten_dict_to_list)
    return tmp_df
