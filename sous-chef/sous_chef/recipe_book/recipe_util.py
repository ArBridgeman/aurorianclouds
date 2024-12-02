from dataclasses import dataclass

import pandas as pd
import pandera as pa
from pandera.typing import Series
from sous_chef.abstract.search_dataframe import DirectSearchError

from utilities.extended_enum import ExtendedEnum


class RecipeSchema(pa.SchemaModel):
    title: Series[str] = pa.Field(nullable=False)
    # TODO set to only timedelta (NaT)
    # but needs to propagate & work with pandera
    time_preparation: Series[pd.Timedelta] = pa.Field(
        nullable=True, coerce=True
    )
    time_cooking: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    time_inactive: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    time_total: Series[pd.Timedelta] = pa.Field(nullable=True, coerce=True)
    # TODO one day set to False, but sometimes extraction issue
    ingredients: Series[str] = pa.Field(nullable=True)
    instructions: Series[str] = pa.Field(nullable=True)
    rating: Series[float] = pa.Field(nullable=True, coerce=True)
    favorite: Series[bool] = pa.Field(nullable=False, coerce=True)
    categories: Series[object] = pa.Field(nullable=False)
    # Raw string indicating recipe yield
    output: Series[str] = pa.Field(nullable=True)
    # Parsed pint quantity from recipe yield
    # TODO fix pandera issue with this
    # quantity: Series[Quantity] = pa.Field(nullable=True)
    tags: Series[object] = pa.Field(nullable=False)
    uuid: Series[str] = pa.Field(unique=True)
    url: Series[str] = pa.Field(nullable=True)
    # TODO simplify logic & get rid of
    factor: Series[float] = pa.Field(nullable=False, coerce=True)
    amount: Series[str] = pa.Field(nullable=True)

    class Config:
        coerce = True
        # strict = True


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
