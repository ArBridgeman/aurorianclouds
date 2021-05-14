#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Utilities related to food items and nutrition information.
#
#
import pyarrow.feather as feather
from fuzzywuzzy import fuzz, process

macro_mapping = {
    "American Indian/Alaska Native Foods": "Prepared",
    "Baby Foods": "Prepared",
    "Baked Products": "Prepared",
    "Beef Products": "Meats",
    "Beverages": "Beverages",
    "Breakfast Cereals": "Prepared",
    "Cereal Grains and Pasta": "Pasta and grains",
    "Dairy and Egg Products": "Dairy products",
    "Fast Foods": "Prepared",
    "Fats and Oils": "Fats and oils",
    "Finfish and Shellfish Products": "Fish",
    "Fruits and Fruit Juices": "Fruits",
    "Lamb, Veal, and Game Products": "Meats",
    "Legumes and Legume Products": "Legumes",
    "Meals, Entrees, and Side Dishes": "Prepared",
    "Nut and Seed Products": "Nuts and seeds",
    "Pork Products": "Meats",
    "Poultry Products": "Meats",
    "Restaurant Foods": "Prepared",
    "Sausages and Luncheon Meats": "Meats",
    "Snacks": "Prepared",
    "Soups, Sauces, and Gravies": "Sauces",
    "Spices and Herbs": "Spices and herbs",
    "Sweets": "Prepared",
    "Vegetables and Vegetable Products": "Vegetables"
}

# mapping translation before pushing to todoist, can be easily changed without changing internal groups
todoist_mapping = {
    "Baking": "Sweet carolina",
    "Beans": "Sauces cans and oils",
    "Legumes": "Sauces cans and oils",
    "Beverages": "Juices and beverages",
    "Canned": "Sauces cans and oils",
    "Cleaning": "Household",
    "Dairy products": "Dairy force",
    "Fats and oils": "Sauces cans and oils",
    "Fish": "Dead animal society",
    "Frozen goods": "Frozen 3",
    "Fruits": "Farmland pride",
    "Grains": "GF park",
    "Juices": "Juices and beverages",
    "Meats": "Dead animal society",
    "Nuts and seeds": "GF park",
    "Other": "Other",
    "Pasta and grains": "GF park",
    "Pasta": "GF park",
    "Prepared": "Other",
    "Sauces": "Sauces cans and oils",
    "Spices and herbs": "Spices and herbs",
    "Unknown": "Other",
    "Vegetables": "Farmland pride"
}

relevant_macro_groups = sorted(
    [
        "Legumes",
        "Beverages",
        "Dairy products",
        "Fats and oils",
        "Fish",
        "Frozen goods",
        "Fruits",
        "Grains",
        "Juices",
        "Meats",
        "Nuts and seeds",
        "Other",
        "Pasta and grains",
        "Pasta",
        "Sauces",
        "Spices and herbs",
        "Vegetables"
    ]
)

not_mappable_group = "Unknown"


def get_fuzzy_match(item_to_match, list_of_search_items, scorer=fuzz.ratio, limit=3,
                    warn=True, warn_thresh=75, reject=0):
    """
    Simple helper function that returns best fuzzy match for item_to_match
    within list_of_search_items.
    Will return best found match and corresponding scorer accuracy, and will by default
    warn if match accuracy is bad.
    """
    from fuzzywuzzy import process

    if item_to_match in list_of_search_items:
        return [(item_to_match, 100)]

    best_results = process.extract(
        item_to_match, list_of_search_items, scorer=scorer, limit=limit
    )
    best_match = best_results[0][0]
    match_quality = best_results[0][1]

    if warn:
        if match_quality < warn_thresh:
            print("Warning! Bad fuzzy search result for item {:s}: {:s} [{:d}]".
                  format(item_to_match, best_match, match_quality))
    if match_quality < reject:
        best_results = [("Unknown", match_quality)]

    return best_results


class IngredientsHelper(object):
    def __init__(self, path_ingredients):
        self.path_ingredients = path_ingredients
        self.ingredient_df = feather.read_feather(self.path_ingredients)

        # calculating macro groups (of interest to us)
        self.ingredient_df["macro_group"] = self.ingredient_df.group_name.apply(
            self.get_group_mapping
        )

        # selection of relevant macro groups
        self.ingredient_df = self.ingredient_df[
            self.ingredient_df.macro_group.isin(relevant_macro_groups)
        ]

        # experimental split and get anything before raw
        self.ingredient_df["desc_long"] = self.ingredient_df.desc_long.str.split(
            ", raw"
        ).str.get(0)

        self.ingredient_df["desc_long"] = self.ingredient_df.desc_long.str.replace("cheese, ", "")

        # sorting according to length of description (to try to optimize fuzzy search)
        self.ingredient_df.sort_values("desc_len", ascending=True, inplace=True)

        # first part of description added as a separate column (typically contains the relevant keyword)
        self.ingredient_df["desc_first"] = self.ingredient_df.desc_long.str.split(
            ","
        ).str.get(0)

        # 2nd part is sometimes also really insightful as first part is sometimes dummy prefix like Fish,
        self.ingredient_df["desc_second"] = (
            self.ingredient_df.desc_long.str.split(",").str.get(1).fillna("")
        )

    @staticmethod
    def manual_overwrites(item):
        # manual overwrites for certain entries
        if "juice" in item:
            return "Juices"
        if "milk" in item and len(item) < 7:
            return "Dairy products"
        if "steak" in item and "sauce" not in item:
            return "Meats"
        if "sauce" in item:
            return "Sauces"
        if "frozen" in item:
            return "Frozen goods"
        if "wine" in item and not "vinegar" in item:
            return "Beverages"
        if "vinegar" in item:
            return "Sauces"
        if "protein bar" in item:
            return "Prepared"
        return None

    def get_food_group_majority_vote(self, item):
        from difflib import get_close_matches

        item = str(item).lower()

        manual = self.manual_overwrites(item)
        if manual is not None:
            return manual

        # matches = get_close_matches(item, self.ingredient_df.desc_long.values,
        #                             n=100, cutoff=0.6)

        matches = get_fuzzy_match(item,
                                  self.ingredient_df.desc_long.values,
                                  scorer=fuzz.WRatio,
                                  limit=10,
                                  )
        matches = [m[0] for m in matches if m[1] > 50]  # get only relevant tuple entries

        matches_df = self.ingredient_df[self.ingredient_df.desc_long.isin(matches)]

        return matches_df.macro_group.mode().iloc[0]

    def get_food_group(self, item, defensive=True):
        item = str(item).lower()

        manual = self.manual_overwrites(item)
        if manual is not None:
            return manual

        # TODO: find better/more universal matching algorithm as below numbers are purely empirical

        # first stage, try search in full description (fails for short items)
        best_result, match_quality = get_fuzzy_match(item,
                                                     self.ingredient_df.desc_long.values,
                                                     scorer=fuzz.QRatio)[0]
        match_df = self.ingredient_df[self.ingredient_df.desc_long == best_result]

        # if match_quality < 75:
        #     best_result, match_quality = get_fuzzy_match(item,
        #                                                  self.ingredient_df.desc_long.values,
        #                                                  scorer=fuzz.partial_ratio)[0]
        #     match_df = self.ingredient_df[self.ingredient_df.desc_long == best_result]

        if match_quality < 70:
            best_result, match_quality = get_fuzzy_match(item,
                                                         self.ingredient_df.desc_first.values,
                                                         scorer=fuzz.QRatio)[0]
            match_df = self.ingredient_df[self.ingredient_df.desc_first == best_result]

            best_result2, match_quality2 = get_fuzzy_match(item,
                                                           self.ingredient_df.desc_second.values,
                                                           scorer=fuzz.QRatio)[0]

            if match_quality2 > match_quality:
                match_quality = match_quality2
                match_df = self.ingredient_df[self.ingredient_df.desc_second == best_result2]

        assert len(match_df) > 0, "No results found!"

        if match_quality < 60:
            print("Warning! Bad mapping quality for ingredient: {:s}".format(item))
            print("Best match: {:s}".format(best_result))

            try:
                return self.get_food_group_majority_vote(item)
            except:
                print("Warning! Could also not get a match with majority vote strategy!")

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
