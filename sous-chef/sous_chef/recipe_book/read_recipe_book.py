import re
from collections import namedtuple
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable, List, Tuple

import pandas as pd
import pandera as pa
from pandera.typing import Series
from sous_chef.abstract.extended_enum import ExtendedEnum
from sous_chef.abstract.pandas_util import get_dict_from_columns
from sous_chef.abstract.search_dataframe import (
    DataframeSearchable,
    DirectSearchError,
    FuzzySearchError,
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


@dataclass
class RecipeNotFoundError(Exception):
    recipe_title: str
    search_results: str
    message: str = "[recipe not found]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} recipe={self.recipe_title} "
            f"search_results=[{self.search_results}]"
        )


# TODO once recipes better parsed, remove & make total_time not null
@dataclass
class RecipeTotalTimeUndefinedError(Exception):
    recipe_title: str
    message: str = "[recipe total time undefined]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} recipe={self.recipe_title}"


class SelectRandomRecipeError(DirectSearchError):
    message = "[select random recipe failed]"


class MapRecipeErrorToException(ExtendedEnum):
    recipe_not_found = RecipeNotFoundError
    recipe_total_time_undefined = RecipeTotalTimeUndefinedError
    random_recipe_selection_failed = SelectRandomRecipeError


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
    recipe_book_path: Path = None
    category_tuple: Tuple = None
    tag_tuple: Tuple = None

    def __post_init__(self):
        self.recipe_book_path = Path(HOME_PATH, self.config.path)
        self._read_category_tuple()
        self._read_tag_tuple()
        # load basic recipe book to self.dataframe
        self._read_recipe_book()
        if self.config.deduplicate:
            self._select_highest_rated_when_duplicated_name()

    def get_random_recipe_by_category(
        self,
        category: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
    ) -> Recipe:
        return self._select_random_recipe_weighted_by_rating(
            method_match=self._is_value_in_list,
            field="categories",
            search_term=category,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
        )

    def get_random_recipe_by_tag(
        self,
        tag: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
    ) -> Recipe:
        return self._select_random_recipe_weighted_by_rating(
            method_match=self._is_value_in_list,
            field="tags",
            search_term=tag,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
        )

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

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term.casefold() in row

    def _read_category_tuple(self):
        category_df = pd.read_json(
            self.recipe_book_path / self.config.file_categories
        )
        self.category_tuple = tuple(category_df.title.values)

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
        self.dataframe = Recipe.validate(self.dataframe)
        num_rated = sum(~self.dataframe.rating.isnull())
        FILE_LOGGER.info(
            "Recipe book stats",
            num_rated=num_rated,
            num_total=self.dataframe.shape[0],
        )

    def _read_tag_tuple(self):
        tag_df = pd.read_json(self.recipe_book_path / self.config.file_tags)
        self.tag_tuple = tuple(tag_df.title.values)

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
        self,
        method_match: Callable,
        field: str,
        search_term: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
    ):
        config_random = self.config.random_select
        mask_selection = self.dataframe[field].apply(
            lambda row: method_match(row, search_term)
        )

        if exclude_uuid_list is not None:
            mask_selection &= ~self.dataframe.uuid.isin(exclude_uuid_list)
        if max_cook_active_minutes is not None:
            # ok, as will later raise exception if
            # selected and total_time is null
            cook_active_time = self.dataframe.time_total.fillna(
                timedelta(minutes=0)
            ) - self.dataframe.time_inactive.fillna(timedelta(minutes=0))
            cook_active_minutes = cook_active_time.dt.total_seconds() / 60
            mask_selection &= cook_active_minutes <= max_cook_active_minutes

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
            random_recipe = result_df.sample(n=1, weights=weighting).iloc[0]
            self._check_total_time(random_recipe)
            return random_recipe
        raise SelectRandomRecipeError(field=field, search_term=search_term)

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
                r"^(\d?\s\d+[\.\,\/]?\d*)?\s([\s\-\_\w\%]+)", row_entry
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
