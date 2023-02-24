import re
from dataclasses import dataclass
from datetime import timedelta
from typing import List

import pandas as pd
from sous_chef.recipe_book._recipe_book import Recipe, RecipeBasic
from sous_chef.recipe_book.recipe_util import (
    RecipeLabelNotFoundError,
    SelectRandomRecipeError,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class RecipeRandomizer(RecipeBasic):
    def get_random_recipe_by_category(
        self,
        category: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
        min_rating: float = None,
    ) -> Recipe:
        if category.lower() not in self.category_tuple:
            raise RecipeLabelNotFoundError(
                field="category", search_term=category
            )
        mask_label_selection = self.dataframe["categories"].apply(
            lambda row: self._is_value_in_list(row, category)
        )
        return self._select_random_recipe_weighted_by_rating(
            mask_label_selection=mask_label_selection,
            field="categories",
            search_term=category,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
            min_rating=min_rating,
        )

    def get_random_recipe_by_filter(
        self,
        filter_str: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
        min_rating: float = None,
    ) -> Recipe:
        mask_label_selection = self.dataframe.apply(
            lambda row: self._construct_filter(row, filter_str), axis=1
        )
        return self._select_random_recipe_weighted_by_rating(
            mask_label_selection=mask_label_selection,
            field="filter",
            search_term=filter_str,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
            min_rating=min_rating,
        )

    def get_random_recipe_by_tag(
        self,
        tag: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
        min_rating: float = None,
    ) -> Recipe:
        if tag.lower() not in self.tag_tuple:
            raise RecipeLabelNotFoundError(field="tag", search_term=tag)

        mask_label_selection = self.dataframe["tags"].apply(
            lambda row: self._is_value_in_list(row, tag)
        )
        return self._select_random_recipe_weighted_by_rating(
            mask_label_selection=mask_label_selection,
            field="tags",
            search_term=tag,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
            min_rating=min_rating,
        )

    def _construct_filter(self, row: pd.Series, filter_str: str):
        def _replace_entity(entity_name: str, match_obj: re.Match) -> str:
            row_name_map = {"tag": "tags", "category": "categories"}
            if (entity := match_obj.group(1)) is not None:
                if entity.lower() not in getattr(self, f"{entity_name}_tuple"):
                    raise RecipeLabelNotFoundError(
                        field=entity_name, search_term=entity
                    )
                return (
                    f"('{entity.lower()}' in {row[row_name_map[entity_name]]})"
                )

        for entity_i in ["category", "tag"]:
            filter_str = re.sub(
                rf"{entity_i[0]}\.([\w\-/]+)",
                lambda x: _replace_entity(entity_i, x),
                filter_str,
            )
        return eval(filter_str)

    def _construct_mask(
        self,
        mask_label_selection,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
        min_rating: float = None,
    ):
        mask_selection = mask_label_selection
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
        if min_rating is not None:
            mask_selection &= self.dataframe.rating >= min_rating
        return mask_selection

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term.casefold() in row

    def _select_random_recipe_weighted_by_rating(
        self,
        mask_label_selection,
        field: str,
        search_term: str,
        exclude_uuid_list: List = None,
        max_cook_active_minutes: float = None,
        min_rating: float = None,
    ):
        config_random = self.config.random_select

        mask_selection = self._construct_mask(
            mask_label_selection=mask_label_selection,
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
            min_rating=min_rating,
        )

        if (count := sum(mask_selection)) < config_random.min_thresh_warning:
            FILE_LOGGER.warning(
                "[select random recipe]",
                selection=f"{field}={search_term}",
                warning=f"only {count} entries available",
                thresh=config_random.min_thresh_warning,
            )
            if count <= config_random.min_thresh_error:
                raise SelectRandomRecipeError(
                    field=field, search_term=search_term
                )

        result_df = self.dataframe[mask_selection]
        weighting = result_df.rating.copy(deep=True).fillna(
            config_random.default_rating
        )
        random_recipe = result_df.sample(n=1, weights=weighting).iloc[0]
        self._check_total_time(random_recipe)
        return random_recipe
