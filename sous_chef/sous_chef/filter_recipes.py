from typing import List

import numpy as np


def check_recipe_for_tag(recipe_tags, desired_tag):
    return desired_tag in recipe_tags


# TODO add type for dataframe
def create_tags_and_filter(recipes, tags: List[str]):
    mask = np.array([True] * recipes.shape[0])
    for tag in tags:
        mask &= recipes.tags.apply(check_recipe_for_tag,
                                   args=(tag,))
    return mask
