import uuid
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.recipe_book.read_recipe_book import (
    Recipe,
    RecipeBook,
    SelectRandomRecipeError,
)
from tests.unit_tests.util import assert_equal_dataframe


@pytest.fixture
def random_seed():
    np.random.seed(42)


@pytest.fixture
def config_recipe_book():
    with initialize(config_path="../../../config"):
        config = compose(config_name="recipe_book")
        return config.recipe_book


@pytest.fixture
def recipe_book(config_recipe_book):
    with patch.object(RecipeBook, "__post_init__"):
        return RecipeBook(config_recipe_book)


class RecipeBookBuilder:
    recipe_book: pd.DataFrame = None

    def add_recipe(self, recipe: pd.DataFrame):
        if self.recipe_book is None:
            self.recipe_book = recipe
        else:
            self.recipe_book = pd.concat([self.recipe_book, recipe])
        return self

    def add_recipe_list(self, recipe_list: list[pd.DataFrame]):
        for recipe in recipe_list:
            self.add_recipe(recipe)
        return self

    @staticmethod
    def convert_recipe_row_to_recipe(row: pd.DataFrame) -> Recipe:
        row = row.squeeze()
        return Recipe(
            title=row.title,
            rating=row.rating,
            ingredient_field=row.ingredients,
            total_cook_time=row.totalTime,
        )

    @staticmethod
    def create_recipe(
        title: str = "Roasted corn salsa",
        preparation_time: pd.Timedelta = pd.Timedelta(minutes=5),
        cooking_time: pd.Timedelta = pd.Timedelta(minutes=15),
        ingredients: str = "100 g sweet corn\n0.5 red onion",
        instructions: str = "Heat frying pan on high heat",
        rating: float = 4.0,
        favorite: bool = False,
        categories: list[str] = None,
        quantity: str = "2 Ariel sides",
        tags: list[str] = None,
    ) -> pd.DataFrame:
        if categories is None:
            categories = ["Side/veggie"]
        if tags is None:
            tags = ["cuisine/Mexican", "ariel/poison"]

        return pd.DataFrame(
            {
                "title": [title],
                "preparationTime": [preparation_time],
                "cookingTime": [cooking_time],
                "totalTime": [preparation_time + cooking_time],
                "ingredients": [ingredients],
                "instructions": [instructions],
                "rating": [rating],
                "favorite": [favorite],
                "categories": [categories],
                "quantity": [quantity],
                "tags": [tags],
                "uuid": [uuid.uuid1()],
            },
            index=[0],
        )

    def get_recipe_book(self):
        return self.recipe_book


@pytest.fixture
def recipe_book_builder():
    return RecipeBookBuilder()


class TestRecipeBook:
    @staticmethod
    @pytest.mark.parametrize(
        "title", ["Romano chicken", "Pasta Salad", "caesar salad"]
    )
    def test_get_recipe_by_title(recipe_book, recipe_book_builder, title):
        recipe = recipe_book_builder.create_recipe(title=title)
        recipe_book.dataframe = recipe_book_builder.add_recipe_list(
            [recipe_book_builder.create_recipe(), recipe]
        ).get_recipe_book()

        result = recipe_book.get_recipe_by_title(title.casefold())
        assert result == recipe_book_builder.convert_recipe_row_to_recipe(
            recipe
        )

    @staticmethod
    @pytest.mark.parametrize(
        "search_term,expected_result",
        [("found_me", True), ("do_not_find_me", False)],
    )
    def test__is_value_in_list(
        recipe_book, recipe_book_builder, search_term, expected_result
    ):
        recipe = recipe_book_builder.create_recipe(tags=["found_me"]).squeeze()

        assert (
            recipe_book._is_value_in_list(recipe.tags, search_term)
            is expected_result
        )

    @staticmethod
    @pytest.mark.parametrize(
        "method,item_type",
        [
            ("get_random_recipe_by_category", "categories"),
            (
                "get_random_recipe_by_tag",
                "tags",
            ),
        ],
    )
    def test__select_random_recipe_weighted_by_rating(
        config_recipe_book,
        recipe_book,
        random_seed,
        recipe_book_builder,
        log,
        method,
        item_type,
    ):
        config_recipe_book.random_select.min_thresh_warning = 5

        search_term = "search_term"
        search_dict = {item_type: [search_term]}
        recipe = recipe_book_builder.create_recipe(
            title="chosen one", rating=4.5, **search_dict
        )
        recipe_book.dataframe = recipe_book_builder.add_recipe_list(
            [
                recipe_book_builder.create_recipe(
                    title="not chosen", rating=0.5, **search_dict
                ),
                recipe_book_builder.create_recipe(
                    title="not chosen2", rating=0.5, **search_dict
                ),
                recipe,
            ]
        ).get_recipe_book()

        result = getattr(recipe_book, method)(search_term)
        assert result == recipe_book_builder.convert_recipe_row_to_recipe(
            recipe
        )
        assert log.events == [
            {
                "event": "[select random recipe]",
                "level": "warning",
                "selection": f"{item_type}=search_term",
                "thresh": 5,
                "warning": "only 3 entries available",
            }
        ]

    @staticmethod
    def test__select_random_recipe_weighted_by_rating_raise_error(
        recipe_book, recipe_book_builder
    ):
        search_term = "search_term"
        tags = [f"not_{search_term}"]
        recipe_book.dataframe = recipe_book_builder.add_recipe(
            recipe_book_builder.create_recipe(tags=tags)
        ).get_recipe_book()

        with pytest.raises(SelectRandomRecipeError):
            recipe_book.get_random_recipe_by_tag(search_term)

    @staticmethod
    @pytest.mark.parametrize(
        "recipe1_rating,recipe2_rating,expected_recipe",
        [
            (0.5, 4.0, "recipe2"),
            (4.0, 0.5, "recipe1"),
        ],
    )
    def test__select_highest_rated_when_duplicated_name(
        recipe_book,
        recipe_book_builder,
        recipe1_rating,
        recipe2_rating,
        expected_recipe,
    ):
        recipe1 = recipe_book_builder.create_recipe(rating=recipe1_rating)
        recipe2 = recipe_book_builder.create_recipe(rating=recipe2_rating)
        recipe_book.dataframe = recipe_book_builder.add_recipe_list(
            [recipe1, recipe2]
        ).get_recipe_book()

        recipe_book._select_highest_rated_when_duplicated_name()

        if expected_recipe == "recipe1":
            assert_equal_dataframe(recipe_book.dataframe, recipe1)
        else:
            assert_equal_dataframe(recipe_book.dataframe, recipe2)
