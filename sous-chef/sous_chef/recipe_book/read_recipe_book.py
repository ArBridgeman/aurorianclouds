import re
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd
import pandera as pa
from pandera.typing import Series
from sous_chef.abstract.pandas_util import get_dict_from_columns
from sous_chef.abstract.search_dataframe import (
    DataframeSearchable,
    DirectSearchError,
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
    ]
)


class SelectRandomRecipeError(DirectSearchError):
    message = "[select random recipe failed]"


class Recipe(pa.SchemaModel):
    title: Series[str] = pa.Field(nullable=False)
    time_preparation: Series[pd.Timedelta] = pa.Field(
        nullable=True, coerce=True
    )
    time_cooking: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    time_inactive: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    time_total: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    ingredients: Series[str] = pa.Field(nullable=False)
    instructions: Series[str] = pa.Field(nullable=True)
    rating: Series[float] = pa.Field(nullable=True, coerce=True)
    favorite: Series[bool] = pa.Field(nullable=False, coerce=True)
    categories: Series[object] = pa.Field(nullable=False)
    quantity: Series[str] = pa.Field(nullable=True)
    tags: Series[object] = pa.Field(nullable=False)
    uuid: Series[str] = pa.Field(unique=True)
    # TODO simplify logic & get rid of
    factor: Series[float] = pa.Field(nullable=False, coerce=True)
    amount: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True


@dataclass
class RecipeBook(DataframeSearchable):
    menu_history: pd.DataFrame = None

    def __post_init__(self):
        # load basic recipe book to self.dataframe
        self._read_recipe_book()
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

    def get_recipe_by_title(self, title) -> pd.Series:
        return self.retrieve_match(field="title", search_term=title)

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

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term.casefold() in row

    def _read_recipe_book(self):
        recipe_book_path = Path(HOME_PATH, self.config.path)
        self.dataframe = pd.concat(
            [
                self._retrieve_format_recipe_df(recipe_file)
                for recipe_file in recipe_book_path.glob(
                    self.config.file_pattern
                )
            ]
        )
        self.dataframe["factor"] = 1
        self.dataframe["amount"] = None
        self.dataframe = Recipe.validate(self.dataframe)

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

    def _select_random_recipe_weighted_by_rating(
        self, method_match: Callable, field: str, search_term: str
    ):
        config_random = self.config.random_select
        mask_selection = self.dataframe[field].apply(
            lambda row: method_match(row, search_term)
        )
        if self.menu_history is not None:
            mask_selection &= ~self.dataframe.uuid.isin(
                self.menu_history.uuid.values
            )
        if (count := sum(mask_selection)) > config_random.min_thresh_error:
            if count < config_random.min_thresh_warning:
                FILE_LOGGER.warning(
                    "[select random recipe]",
                    selection=f"{field}={search_term}",
                    warning=f"only {count} entries available",
                    thresh=config_random.min_thresh_warning,
                )

            result_df = self.dataframe[mask_selection]
            weighting = (
                result_df.rating.copy(deep=True)
                .fillna(0)
                .replace(0, config_random.default_rating)
            )
            return result_df.sample(n=1, weights=weighting).iloc[0]
        raise SelectRandomRecipeError(field=field, search_term=search_term)

    def _select_highest_rated_when_duplicated_name(self):
        self.dataframe = self.dataframe.sort_values(["rating"], ascending=False)
        self.dataframe = self.dataframe.drop_duplicates(["title"], keep="first")


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
        row_entry = re.sub(r"mins\.?", "min", row_entry)
        row_entry = re.sub(r"hrs\.?", "hour", row_entry)
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

        if row_entry == "":
            return pd.NaT

        # errors = "ignore", if confident we want to ignore further issues
        time_converted = pd.to_timedelta(row_entry, unit=None, errors="coerce")
        if time_converted is pd.NaT:
            FILE_LOGGER.warning(
                "[create_timedelta] conversion failed", entry=row_entry
            )

        return time_converted
