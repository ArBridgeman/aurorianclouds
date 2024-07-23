from dataclasses import dataclass
from typing import Optional

import pandas as pd
import pandera as pa
from pandera.engines.pandas_engine import PydanticModel
from pint import Quantity
from pydantic import BaseModel, Field
from sous_chef.abstract.extended_enum import ExtendedEnum
from sous_chef.abstract.search_dataframe import DirectSearchError


def convert_nat_to_none(value: pd.Timedelta) -> Optional[pd.Timedelta]:
    if isinstance(value, pd.Timedelta) and pd.isna(value):
        return None
    return value


class Recipe(BaseModel):
    title: str
    # TODO set to only timedelta (NaT)
    # but needs to propagate & work with pandera
    time_preparation: Optional[pd.Timedelta]
    time_cooking: Optional[pd.Timedelta]
    time_inactive: Optional[pd.Timedelta]
    time_total: Optional[pd.Timedelta]
    # TODO one day set to False, but sometimes extraction issue
    ingredients: Optional[str]
    instructions: Optional[str]
    rating: Optional[float]
    favorite: bool
    categories: object
    output: Optional[str] = Field(
        description="Not parsed string indicating recipe yield"
    )
    quantity: Optional[Quantity] = Field(
        description="Parsed pint quantity from recipe yield"
    )
    tags: object
    uuid: str = pa.Field(unique=True)
    url: Optional[str]
    factor: float
    amount: Optional[str]

    class Config:
        arbitrary_types_allowed = True


class RecipeSchema(pa.SchemaModel):
    class Config:
        dtype = PydanticModel(Recipe)
        coerce = True  # required


@dataclass
class RecipeLabelNotFoundError(Exception):
    field: str
    search_term: str
    message: str = "[recipe label not found]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} field={self.field} "
            f"search_term={self.search_term}"
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
