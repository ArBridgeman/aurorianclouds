import pytest
import pathlib
from sous_chef.utils_groceries import IngredientsHelper

# TODO: refactor and put files somewhere else or have better way to specify path
data_base = pathlib.Path.cwd() / ".." / ".." / "nutrition_data"
path_input = data_base / "food_items.feather"

ingredient_helper = IngredientsHelper(path_input)


class TestIngredientsHelper:

    @pytest.mark.parametrize("ingredient,expected_category",
                             [("banana", "Fruits and vegetables"),
                              ("apple", "Fruits and vegetables"),
                              ("apple juice", "Juices"),
                              ("flank steak", "Meats"),
                              ("butter", "Dairy products"),
                              ("milk", "Dairy products"),
                              ("yoghurt", "Dairy products"),
                              ("broccoli", "Fruits and vegetables"),
                              ("avocado", "Fruits and vegetables"),
                              ("beef", "Meats"),
                              ("salmon", "Fish"),
                              ("shrimp", "Fish"),
                              ("cucumber", "Fruits and vegetables"),
                              ("cooking oil", "Fats and oils"),
                              ("soy sauce", "Spices and sauces"),
                              ("white wine", "Beverages"),
                              ("chicken breast", "Meats")
                              ])
    def test_get_food_group(self, ingredient, expected_category):
        assert ingredient_helper.get_food_group(ingredient) == expected_category
