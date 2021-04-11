import pytest
import pathlib
from sous_chef.grocery_list.utils_groceries import IngredientsHelper

# TODO: refactor and put files somewhere else or have better way to specify path
data_base = pathlib.Path.cwd() / ".." / ".." / "nutrition_data"
path_input = data_base / "food_items.feather"

ingredient_helper = IngredientsHelper(path_input)


class TestIngredientsHelper:

    @pytest.mark.parametrize("ingredient,expected_category",
                             [("banana", "Fruits"),
                              ("apple", "Fruits"),
                              ("apple juice", "Juices"),
                              ("flank steak", "Meats"),
                              ("butter", "Dairy products"),
                              ("milk", "Dairy products"),
                              ("yoghurt", "Dairy products"),
                              ("broccoli", "Vegetables"),
                              ("avocado", "Fruits"),
                              ("beef", "Meats"),
                              ("salmon", "Fish"),
                              ("shrimp", "Fish"),
                              ("cucumber", "Vegetables"),
                              ("cooking oil", "Fats and oils"),
                              ("soy sauce", "Sauces"),
                              ("white wine", "Beverages"),
                              ("chicken breast", "Meats"),
                              ("protein bar", "Pasta and grains"),
                              ("rice vinegar", "Sauces"),
                              ("feta", "Dairy products")
                              ])
    def test_get_food_group(self, ingredient, expected_category):
        assert ingredient_helper.get_food_group(ingredient) == expected_category
