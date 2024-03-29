import re
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pandas as pd
from sous_chef.abstract.pandas_util import get_dict_from_columns
from sous_chef.abstract.search_dataframe import (
    DataframeSearchable,
    FuzzySearchError,
)
from sous_chef.recipe_book.recipe_util import (
    Recipe,
    RecipeNotFoundError,
    RecipeTotalTimeUndefinedError,
)
from structlog import get_logger

HOME_PATH = str(Path.home())
FILE_LOGGER = get_logger(__name__)

MAP_FIELD_TO_COL = namedtuple("Map", ["json_field", "df_column", "dtype"])

MAP_JSON_TO_DF = pd.DataFrame(
    data=[
        MAP_FIELD_TO_COL("title", "title", str),
        MAP_FIELD_TO_COL("preparationTime", "time_preparation", str),
        MAP_FIELD_TO_COL("inactiveTime", "time_inactive", str),
        MAP_FIELD_TO_COL("cookingTime", "time_cooking", str),
        MAP_FIELD_TO_COL("totalTime", "time_total", str),
        MAP_FIELD_TO_COL("ingredients", "ingredients", str),
        MAP_FIELD_TO_COL("instructions", "instructions", str),
        MAP_FIELD_TO_COL("rating", "rating", float),
        MAP_FIELD_TO_COL("favorite", "favorite", bool),
        MAP_FIELD_TO_COL("categories", "categories", list),
        # TODO quantity should be split/standardized...it's bad!!!
        MAP_FIELD_TO_COL("quantity", "quantity", str),
        MAP_FIELD_TO_COL("tags", "tags", list),
        MAP_FIELD_TO_COL("uuid", "uuid", str),
        MAP_FIELD_TO_COL("url", "url", str),
    ]
)


@dataclass
class RecipeBasic(DataframeSearchable):
    recipe_book_path: Path = None
    category_tuple: Tuple = tuple()
    tag_tuple: Tuple = tuple()

    def __post_init__(self):
        self.recipe_book_path = Path(HOME_PATH, self.config.path)
        self._read_category_tuple()
        self._read_tag_tuple()
        # load basic recipe book to self.dataframe
        self._read_recipe_book()
        if self.config.deduplicate:
            self._select_highest_rated_when_duplicated_name()

    def get_recipe_by_title(self, title) -> pd.Series:
        try:
            recipe = self.retrieve_match(field="title", search_term=title)
            self._check_total_time(recipe)
            return recipe.copy(deep=True)
        except FuzzySearchError as e:
            raise RecipeNotFoundError(recipe_title=title, search_results=str(e))

    @staticmethod
    def _check_total_time(recipe: pd.Series):
        if recipe.time_total is pd.NaT:
            raise RecipeTotalTimeUndefinedError(recipe_title=recipe.title)

    @staticmethod
    def _flatten_dict_to_list(cell: list[dict]) -> list[str]:
        if not isinstance(cell, list):
            return []
        return [entry["title"].casefold() for entry in cell]

    def _format_recipe_row(self, row: pd.Series) -> pd.Series:
        FILE_LOGGER.info("[format recipe row]", recipe=row.title)
        for time_col in [
            "time_total",
            "time_preparation",
            "time_cooking",
            "time_inactive",
        ]:
            row[time_col] = create_timedelta(row[time_col])
        for col in ["categories", "tags"]:
            row[col] = self._flatten_dict_to_list(row[col])
        return row

    def _read_category_tuple(self):
        category_df = pd.read_json(
            self.recipe_book_path / self.config.file_categories
        )
        self.category_tuple = tuple(category_df.title.str.lower().values)

    def _read_recipe_book(self):
        self.dataframe = pd.concat(
            [
                self._retrieve_format_recipe_df(recipe_file)
                for recipe_file in self.recipe_book_path.glob(
                    self.config.file_recipe_pattern
                )
            ]
        )
        self.dataframe["factor"] = 1
        self.dataframe["amount"] = None
        self.dataframe.replace("nan", pd.NA, inplace=True)
        self.dataframe.time_inactive.replace(pd.NA, 0, inplace=True)
        self.dataframe = Recipe.validate(self.dataframe)
        num_rated = sum(~self.dataframe.rating.isnull())
        FILE_LOGGER.info(
            "Recipe book stats",
            num_rated=num_rated,
            num_total=self.dataframe.shape[0],
        )

    def _read_tag_tuple(self):
        tag_df = pd.read_json(self.recipe_book_path / self.config.file_tags)
        self.tag_tuple = tuple(tag_df.title.str.lower().values)

    def _retrieve_format_recipe_df(self, json_file):
        tmp_df = pd.read_json(
            json_file,
            dtype=get_dict_from_columns(
                df=MAP_JSON_TO_DF, key_col="json_field", value_col="dtype"
            ),
        )
        for col in MAP_JSON_TO_DF.json_field:
            if col not in tmp_df.columns:
                tmp_df[col] = None
        tmp_df = tmp_df[MAP_JSON_TO_DF.json_field].rename(
            columns=get_dict_from_columns(
                df=MAP_JSON_TO_DF, key_col="json_field", value_col="df_column"
            )
        )
        return tmp_df.apply(self._format_recipe_row, axis=1)

    def _select_highest_rated_when_duplicated_name(self):
        self.dataframe = self.dataframe.sort_values(["rating"], ascending=False)
        self.dataframe = self.dataframe.drop_duplicates(["title"], keep="first")


def create_timedelta(row_entry):
    from fractions import Fraction

    if row_entry == "" or row_entry is None:
        return ""

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
        row_entry = re.sub(r"mins\.?", "min", row_entry)
        row_entry = re.sub(r"hrs\.?", "hour", row_entry)
        if re.match(r"^\d{1,2}:\d{1,2}$", row_entry):
            row_entry = "{}:00".format(row_entry)

        # handle fractions properly
        # todo outsource to separate clean function
        if "/" in row_entry:
            groups = re.match(
                r"^(\d?\s\d+[.,/]?\d*)?\s([\s\-_\w%]+)", row_entry
            )
            if groups:
                float_conv = float(
                    sum(Fraction(s) for s in groups.group(1).split())
                )
                row_entry = f"{float_conv} {groups.group(2).strip()}"

        # errors = "ignore", if confident we want to ignore further issues
        time_converted = pd.to_timedelta(row_entry, unit=None, errors="coerce")
        if time_converted is pd.NaT:
            FILE_LOGGER.warning(
                "[create_timedelta] conversion failed", entry=row_entry
            )

        return time_converted
