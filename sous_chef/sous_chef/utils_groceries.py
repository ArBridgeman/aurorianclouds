#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Utilities related to food items and nutrition information.
#
#
import pyarrow.feather as feather
from fuzzywuzzy import fuzz, process

macro_mapping = {
    "Dairy and Egg Products": "Dairy products",
    "Spices and Herbs": "Spices and sauces",
    "Baby Foods": "Prepared",
    "Fats and Oils": "Fats and oils",
    "Poultry Products": "Meats",
    "Soups, Sauces, and Gravies": "Spices and sauces",
    "Sausages and Luncheon Meats": "Meats",
    "Breakfast Cereals": "Prepared",
    "Snacks": "Prepared",
    "Fruits and Fruit Juices": "Fruits and vegetables",
    "Pork Products": "Meats",
    "Vegetables and Vegetable Products": "Fruits and vegetables",
    "Nut and Seed Products": "Pasta, grains, nuts, seeds",
    "Beef Products": "Meats",
    "Beverages": "Beverages",
    "Finfish and Shellfish Products": "Fish",
    "Legumes and Legume Products": "Pasta, grains, nuts, seeds",
    "Lamb, Veal, and Game Products": "Meats",
    "Baked Products": "Prepared",
    "Sweets": "Prepared",
    "Cereal Grains and Pasta": "Pasta, grains, nuts, seeds",
    "Fast Foods": "Prepared",
    "Meals, Entrees, and Side Dishes": "Prepared",
    "American Indian/Alaska Native Foods": "Prepared",
    "Restaurant Foods": "Prepared"
}

relevant_macro_groups = ["Meats", "Fruits and vegetables", "Pasta, grains, nuts, seeds",
                         "Spices and sauces", "Beverages", "Fish", "Dairy products",
                         "Fats and oils", "Frozen goods"]

not_mappable_group = "Unknown"


class IngredientsHelper(object):

    def __init__(self, path_ingredients):
        self.path_ingredients = path_ingredients
        self.ingredient_df = feather.read_feather(self.path_ingredients)

        # calculating macro groups (of interest to us)
        self.ingredient_df["macro_group"] = self.ingredient_df.group_name.apply(self.get_group_mapping)

        # selection of relevant macro groups
        self.ingredient_df = self.ingredient_df[self.ingredient_df.macro_group.isin(relevant_macro_groups)]

        # sorting according to length of description (to try to optimize fuzzy search)
        self.ingredient_df.sort_values("desc_len", ascending=True, inplace=True)

        # first part of description added as a separate column (typically contains the relevant keyword)
        self.ingredient_df["desc_first"] = self.ingredient_df.desc_long.str.split(",").str.get(0)

        # 2nd part is sometimes also really insightful as first part is sometimes dummy prefix like Fish,
        self.ingredient_df["desc_second"] = self.ingredient_df.desc_long.str.split(",").str.get(1).fillna("")

    def get_food_group(self, item, defensive=True):
        item = str(item).lower()

        # manual overwrites for certain entries
        if "juice" in item:
            return "Juices"
        if "sauce" in item:
            return "Spices and sauces"
        if "frozen" in item:
            return "Frozen goods"

        # first stage, search only in desc_first (first part of total description)
        best_result = process.extract(item,
                                      self.ingredient_df.desc_first.values,
                                      scorer=fuzz.ratio,
                                      limit=3)

        match_df = self.ingredient_df[self.ingredient_df.desc_first == best_result[0][0]]

        if best_result[0][1] < 55:
            best_result = process.extract(item,
                                          self.ingredient_df.desc_second.values,
                                          scorer=fuzz.ratio,
                                          limit=3)
            match_df = self.ingredient_df[self.ingredient_df.desc_second == best_result[0][0]]

        # if mapping quality thus far is bad, try a mapping on full description (more dangerous, though)
        if best_result[0][1] < 50:
            best_result = process.extract(item,
                                          self.ingredient_df.desc_long.values,
                                          scorer=fuzz.ratio,
                                          limit=3)
            match_df = self.ingredient_df[self.ingredient_df.desc_long == best_result[0][0]]

        assert len(match_df) > 0, "No results found!"

        if best_result[0][1] < 50:
            print("Warning! Bad mapping quality for ingredient: {:s}".format(item))
            print("Best match: {:s}".format(best_result[0][0]))

            if defensive:
                return not_mappable_group

        return match_df.iloc[0].macro_group

    # TODO: implement nutrition etc estimation based on USDA data
    def get_nutritional_information(self):
        raise NotImplementedError("Functionality not implemented yet!")

    @staticmethod
    def get_group_mapping(group):
        if group not in macro_mapping.keys():
            return not_mappable_group
        return macro_mapping[group]
