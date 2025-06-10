import hashlib
import re
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import regex
from joblib import Memory
from pint import Quantity
from sous_chef.abstract.pandas_util import get_dict_from_columns
from sous_chef.abstract.search_dataframe import (
    DataframeSearchable,
    FuzzySearchError,
)
from sous_chef.formatter.format_unit import UnitExtractionError, get_pint_repr
from sous_chef.formatter.units import unit_registry
from sous_chef.recipe_book.recipe_util import (
    RecipeNotFoundError,
    RecipeSchema,
    RecipeTotalTimeUndefinedError,
)
from structlog import get_logger

HOME_PATH = str(Path.home())
FILE_LOGGER = get_logger(__name__)

# initialize disk cache
ABS_FILE_PATH = Path(__file__).absolute().parent
CACHE_DIR = ABS_FILE_PATH / "diskcache"

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
        MAP_FIELD_TO_COL("quantity", "output", str),
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

        self._load_pint_quantity()

        if self.config.deduplicate:
            self._select_highest_rated_when_duplicated_name()

    def _load_pint_quantity(self):
        # cannot pickle pint quantities in cache
        quantity_cfg = self.config.quantity
        quantity_patterns = [
            quantity_cfg[prefix_type] + quantity_cfg["unit"]
            for prefix_type in quantity_cfg["prefix_pattern"]
        ]
        self.dataframe["quantity"] = self.dataframe.output.apply(
            lambda x: extract_pint_quantity(
                quantity_patterns=quantity_patterns, recipe_output=x
            )
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

    @staticmethod
    def _format_recipe_row(row: pd.Series) -> pd.Series:
        FILE_LOGGER.info("[format recipe row]", recipe=row.title)
        for time_col in [
            "time_total",
            "time_preparation",
            "time_cooking",
            "time_inactive",
        ]:
            row[time_col] = create_timedelta(row[time_col])
        for col in ["categories", "tags"]:
            row[col] = RecipeBasic._flatten_dict_to_list(row[col])
        return row

    def _read_category_tuple(self):
        category_df = pd.read_json(
            self.recipe_book_path / self.config.file_categories
        )
        self.category_tuple = tuple(category_df.title.str.lower().values)

    def _read_recipe_book(self):
        self.dataframe = read_recipe_book(
            recipe_book_path=self.recipe_book_path,
            recipe_file_pattern=self.config.file_recipe_pattern,
        )
        num_rated = sum(~self.dataframe.rating.isnull())
        FILE_LOGGER.info(
            "Recipe book stats",
            num_rated=num_rated,
            num_total=self.dataframe.shape[0],
        )

    def _read_tag_tuple(self):
        tag_df = pd.read_json(self.recipe_book_path / self.config.file_tags)
        self.tag_tuple = tuple(tag_df.title.str.lower().values)

    @staticmethod
    def retrieve_format_recipe_df(json_file: Path) -> pd.DataFrame:
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
        return tmp_df.apply(RecipeBasic._format_recipe_row, axis=1)

    def _select_highest_rated_when_duplicated_name(self):
        self.dataframe = self.dataframe.sort_values(["rating"], ascending=False)
        self.dataframe = self.dataframe.drop_duplicates(["title"], keep="first")


def create_timedelta_clean_row_entry(row_entry: str) -> str:
    row_entry = row_entry.lower().strip()
    row_entry = re.sub("time", "", row_entry)
    row_entry = re.sub("prep", "", row_entry)
    row_entry = re.sub("cooking", "", row_entry)
    row_entry = re.sub("minut[eo]s.?", "min", row_entry)
    row_entry = re.sub(r"^[\D]+", "", row_entry)
    row_entry = re.sub(r"mins\.?", "min", row_entry)
    row_entry = re.sub(r"mines\.?", "min", row_entry)
    row_entry = re.sub(r"hrs\.?", "hour", row_entry)
    return row_entry


# TODO: check and add test cases or remove if no longer relevant
def create_timedelta_parse_fractions(row_entry: str) -> str:
    from fractions import Fraction

    groups = re.match(r"^(\d?\s\d+[.,/]?\d*)?\s([\s\-_\w%]+)", row_entry)
    if groups:
        float_conv = float(sum(Fraction(s) for s in groups.group(1).split()))
        return f"{float_conv} {groups.group(2).strip()}"
    return pd.NaT


def create_timedelta(row_entry: str) -> pd.Timedelta:
    # some kind of null value
    if pd.isnull(row_entry):
        return pd.NaT

    # string cleaning
    row_entry = create_timedelta_clean_row_entry(row_entry)

    # empty string
    if row_entry == "":
        return pd.NaT

    # if row_entry is a number, assume minutes
    if row_entry.isdecimal():
        return pd.to_timedelta(int(row_entry), unit="minutes")

    # comes in hh:mm format, but without seconds (needed for pandas to convert)
    if re.match(r"^\d{1,2}:\d{1,2}$", row_entry):
        row_entry = f"{row_entry}:00"

    # comes in hh h mm format, but needs min at the end
    if re.match(r"^\d{1,3}\s?h(our)?s?\s?\d{1,2}$", row_entry):
        row_entry = f"{row_entry} min"

    # handle fractions properly
    if "/" in row_entry:
        row_entry = create_timedelta_parse_fractions(row_entry)

    # errors = "ignore", if confident we want to ignore further issues
    time_converted = pd.to_timedelta(row_entry, unit=None, errors="coerce")
    if time_converted is pd.NaT:
        FILE_LOGGER.warning(
            "[create_timedelta] conversion failed", entry=row_entry
        )

    return time_converted


def read_recipe_book(
    recipe_book_path: Path, recipe_file_pattern: str
) -> pd.DataFrame:
    encoded_source_path = str(recipe_book_path).encode()
    hash_obj = hashlib.sha256(encoded_source_path)
    hex_dig = hash_obj.hexdigest()

    cache = Memory(CACHE_DIR / hex_dig, mmap_mode="r")

    recipe_files = [
        recipe_file
        for recipe_file in recipe_book_path.glob(recipe_file_pattern)
    ]

    def is_cache_valid(metadata) -> bool:
        time_cache = metadata["time"]

        if len(recipe_files) == 0:
            return False

        time_recipe_files = max(
            recipe.stat().st_mtime for recipe in recipe_files
        )
        if time_recipe_files > time_cache:
            return False

        return True

    @cache.cache(cache_validation_callback=is_cache_valid)
    def _get_recipe_book() -> pd.DataFrame:
        dataframe = pd.concat(
            [
                RecipeBasic.retrieve_format_recipe_df(recipe_file)
                for recipe_file in recipe_files
            ]
        )
        dataframe["factor"] = 1
        dataframe["amount"] = None
        # cannot pickle pint units at this time
        dataframe["quantity"] = None
        dataframe = dataframe.replace("nan", pd.NA)

        # TODO: can remove?
        dataframe.time_preparation = dataframe.time_preparation.astype(
            "object"
        ).replace(pd.NA, None)
        dataframe.time_cooking = dataframe.time_cooking.astype(
            "object"
        ).replace(pd.NA, None)
        dataframe.time_inactive = dataframe.time_inactive.replace(pd.NA, 0)
        dataframe.time_total = dataframe.time_total.astype("object").replace(
            pd.NA, None
        )

        return RecipeSchema.validate(dataframe)

    return _get_recipe_book()


def extract_pint_quantity(
    quantity_patterns: list, recipe_output: str
) -> Optional[Quantity]:
    if recipe_output is pd.NA or not recipe_output:
        return None

    if recipe_output.isdecimal():
        return float(recipe_output) * unit_registry.dimensionless

    for pattern in quantity_patterns:
        result = regex.match(pattern, recipe_output)
        if result is not None:
            quantity = result.group(1)
            unit = result.group(2)
            try:
                return get_pint_repr(quantity + unit)
            except UnitExtractionError:
                return float(quantity) * unit_registry.dimensionless
