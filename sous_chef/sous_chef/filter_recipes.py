from typing import List

import numpy as np
import pandas as pd
from sous_chef.definitions import PROTEIN_SOURCE


def has_recipe_category_or_tag(recipe_tags, desired_category_or_tag):
    return desired_category_or_tag in recipe_tags


def create_tags_and_filter(recipes: pd.DataFrame, tags: List[str]):
    mask = np.ones(recipes.shape[0], dtype=bool)
    for tag in tags:
        if "not-" in tag:
            reverse_tag = tag.replace("not-", "")
            mask &= ~recipes.tags.apply(has_recipe_category_or_tag, args=(reverse_tag,))
        else:
            mask &= recipes.tags.apply(has_recipe_category_or_tag, args=(tag,))
    return mask


def create_tags_or_filter(recipes: pd.DataFrame, tags: List[str]):
    mask = np.zeros(recipes.shape[0], dtype=bool)
    for tag in tags:
        mask = np.logical_or(
            mask, recipes.tags.apply(has_recipe_category_or_tag, args=(tag,))
        )
    return mask


def create_category_or_filter(recipes, categories: List[str]):
    mask = np.array([False] * recipes.shape[0])
    for category in categories:
        mask = np.logical_or(
            mask, recipes.categories.apply(has_recipe_category_or_tag, args=(category,))
        )
    return mask


def create_protein_filter(recipes, protein_source: str):
    return create_tags_or_filter(recipes, PROTEIN_SOURCE[protein_source])


def create_previously_tried_filter(recipes):
    return recipes.rating > 0.0


# TODO add type for dataframe and timedelta
def create_time_filter(recipes, max_time_minutes):
    return recipes.totalTime <= pd.to_timedelta(max_time_minutes, unit="minutes")


def skip_protein_filter(recipes):
    return ~create_tags_or_filter(recipes, PROTEIN_SOURCE["side_excluded"])
