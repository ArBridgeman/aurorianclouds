import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sous_chef.abstract.search_dataframe import DataframeSearchable
from sous_chef.definitions import (
    CALENDAR_COLUMNS,
    CALENDAR_FILE_PATTERN,
    INP_JSON_COLUMNS,
)
from structlog import get_logger

HOME_PATH = str(Path.home())
FILE_LOGGER = get_logger(__name__)


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
        self._load_basic_recipe_book()

    def get_recipe_by_title(self, title):
        result = self.retrieve_match(field="title", search_term=title)
        return Recipe(
            title=result.title,
            rating=result.rating,
            ingredient_field=result.ingredients,
            total_cook_time=result.totalTime,
        )

    def _load_basic_recipe_book(self):
        self._read_recipe_file()
        if self.config.deduplicate:
            self._select_highest_rated_when_duplicated_name()

    def _read_recipe_file(self):
        recipe_book_path = Path(HOME_PATH, self.config.path)
        for recipe_file in recipe_book_path.glob(self.config.file_pattern):
            self.dataframe = self.dataframe.append(
                retrieve_format_recipe_df(recipe_file)
            )

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


# TODO figure to separate active vs inactive cooking; make resilient to problems
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


def create_food_type(row):
    if "veggies" in row.tags:
        return "veggies"
    elif "starch" in row.tags:
        return "starch"
    elif "Entree" in row.categories:
        return "protein"
    else:
        return "dessert"


def label_calendar(calendar, recipes):
    calendar = pd.merge(
        calendar,
        recipes[["uuid", "tags", "categories"]],
        how="inner",
        left_on="recipeUuid",
        right_on="uuid",
    )
    calendar["food_type"] = calendar.apply(
        lambda x: create_food_type(x), axis=1
    )
    return calendar


def read_calendar(calendar_path, recipes):
    filepath = Path(calendar_path, CALENDAR_FILE_PATTERN)
    calendar = pd.read_json(filepath, dtype=CALENDAR_COLUMNS)[
        CALENDAR_COLUMNS.keys()
    ]
    calendar["date"] = pd.to_datetime(calendar["date"]).dt.date
    return label_calendar(calendar, recipes)
