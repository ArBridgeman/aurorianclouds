from typing import Optional, Union

import pandas as pd
import pandera as pa
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import MealTime, Weekday
from sous_chef.menu.create_menu.exceptions import MenuConfigError

from utilities.extended_enum import ExtendedEnum, ExtendedIntEnum


class TypeProcessOrder(ExtendedIntEnum):
    recipe = 0
    ingredient = 1
    filter = 2
    tag = 3
    category = 4


class RandomSelectType(ExtendedEnum):
    rated = "rated"
    unrated = "unrated"
    either = "either"


class Season(ExtendedEnum):
    any = "0_any"
    winter = "1_winter"
    spring = "2_spring"
    summer = "3_summer"
    fall = "4_fall"


class BasicMenuSchema(pa.SchemaModel):
    # TODO replace all panderas with pydantic & create own validator with
    #  dataframe returned, as no default functions & coerce is poorly made
    weekday: Series[str] = pa.Field(isin=Weekday.name_list("capitalize"))
    meal_time: Series[str] = pa.Field(isin=MealTime.name_list("lower"))
    type: Series[str] = pa.Field(isin=TypeProcessOrder.name_list())
    eat_factor: Series[float] = pa.Field(
        ge=0, default=0, nullable=False, coerce=True
    )
    eat_unit: Series[str] = pa.Field(nullable=True)
    freeze_factor: Series[float] = pa.Field(
        ge=0, default=0, nullable=False, coerce=True
    )
    defrost: Series[str] = pa.Field(
        isin=["Y", "N"], default="N", nullable=False, coerce=True
    )
    item: Series[str]

    class Config:
        strict = True
        coerce = True


class InProgressSchema(BasicMenuSchema):
    selection: Series[str] = pa.Field(
        isin=RandomSelectType.name_list(), nullable=True
    )
    prep_day: Optional[Series[float]] = pa.Field(
        ge=0, lt=7, default=0, nullable=False, coerce=True
    )
    override_check: Series[str] = pa.Field(
        isin=["Y", "N"], default="N", nullable=False, coerce=True
    )


class AllMenuSchema(InProgressSchema):
    menu: Series[int] = pa.Field(ge=0, nullable=False)
    season: Series[str] = pa.Field(isin=Season.value_list(), nullable=False)


class TimeSchema(pa.SchemaModel):
    cook_datetime: Optional[Series[pd.DatetimeTZDtype]] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    prep_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )


class LoadedMenuSchema(InProgressSchema, TimeSchema):
    pass


class TmpMenuSchema(BasicMenuSchema, TimeSchema):
    # override as should be replaced with one of these
    type: Series[str] = pa.Field(isin=["ingredient", "recipe"])
    time_total: Series[pd.Timedelta] = pa.Field(nullable=False, coerce=True)
    # manual ingredients lack these
    rating: Series[float] = pa.Field(nullable=True, coerce=True)
    uuid: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = True


def validate_menu_schema(
    dataframe: Union[DataFrameBase, pd.DataFrame], model
) -> Union[DataFrameBase]:
    if isinstance(dataframe, pd.DataFrame):
        # TODO consider if need sneaky access to hidden method
        selected_cols = model._collect_fields().keys()
        return model.validate(dataframe[selected_cols].copy())
    raise ValueError(f"dataframe is of type {type(dataframe)}")


def get_weekday_from_short(short_week_day: str):
    weekday = Weekday.get_by_abbreviation(short_week_day)
    if not weekday:
        raise MenuConfigError(f"{short_week_day} unknown day!")
    return weekday.name.capitalize()
