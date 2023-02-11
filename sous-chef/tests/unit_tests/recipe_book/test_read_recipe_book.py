import uuid
from dataclasses import dataclass
from typing import List, Tuple, Union
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.recipe_book.read_recipe_book import (
    RecipeBook,
    RecipeLabelNotFoundError,
    RecipeTotalTimeUndefinedError,
    SelectRandomRecipeError,
    create_timedelta,
)
from tests.util import assert_equal_dataframe, assert_equal_series


def get_lowered_tuple(values: List[str]) -> Tuple:
    return tuple(value.lower() for value in values)


@pytest.fixture
def random_seed():
    np.random.seed(42)


@pytest.fixture
def config_recipe_book():
    with initialize(version_base=None, config_path="../../../config"):
        config = compose(config_name="recipe_book")
        return config.recipe_book


@pytest.fixture
def recipe_book(config_recipe_book):
    with patch.object(RecipeBook, "__post_init__"):
        return RecipeBook(config_recipe_book)


@dataclass
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

    def create_recipe(
        self,
        title: str = "Roasted corn salsa",
        preparation_time_str: str = "5 min",
        time_inactive_str: str = "120 min",
        cooking_time_str: str = "15 min",
        ingredients: str = "100 g sweet corn\n0.5 red onion",
        instructions: str = "Heat frying pan on high heat",
        rating: float = 4.0,
        favorite: bool = False,
        categories: Union[list[dict], list[str]] = None,
        quantity: str = "2 Ariel sides",
        tags: Union[list[dict], list[str]] = None,
        uuid_value=uuid.uuid1(),
        post_process_recipe: bool = True,
    ) -> pd.DataFrame:
        categories, tags = self._check_categories_and_tags(
            post_process_recipe, categories, tags
        )

        total_time = (
            pd.to_timedelta(preparation_time_str)
            + pd.to_timedelta(cooking_time_str)
            + pd.to_timedelta(time_inactive_str)
        )

        recipe = {
            "title": [title],
            "time_preparation": [preparation_time_str],
            "time_inactive": [time_inactive_str],
            "time_cooking": [cooking_time_str],
            "time_total": [str(total_time)],
            "ingredients": [ingredients],
            "instructions": [instructions],
            "rating": [rating],
            "favorite": [favorite],
            "categories": [categories],
            "quantity": [quantity],
            "tags": [tags],
            "uuid": [uuid_value],
        }
        if not post_process_recipe:
            return pd.DataFrame(recipe, index=[0])

        recipe["time_preparation"] = pd.to_timedelta(preparation_time_str)
        recipe["time_cooking"] = pd.to_timedelta(cooking_time_str)
        recipe["time_inactive"] = pd.to_timedelta(time_inactive_str)
        recipe["time_total"] = total_time
        return pd.DataFrame(recipe, index=[0])

    @staticmethod
    def _check_categories_and_tags(post_process_recipe, categories, tags):
        if not post_process_recipe:
            if categories is None:
                categories = [{"title": "side/veggie"}]
            if tags is None:
                tags = [{"title": "cuisine/mexican"}, {"title": "ariel/poison"}]
            assert isinstance(categories[0], dict)
            assert isinstance(tags[0], dict)
        else:
            if categories is None:
                categories = ["side/veggie"]
            if tags is None:
                tags = ["cuisine/mexican", "ariel/poison"]
            if len(categories) > 0:
                assert isinstance(categories[0], str)
            if len(tags) > 0:
                assert isinstance(tags[0], str)
        return categories, tags

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
        assert_equal_series(result, recipe.squeeze())

    @staticmethod
    @pytest.mark.parametrize(
        "categories,tags",
        [
            (["Entree/protein"], []),
            ([], ["protein/seafood"]),
            (["Entree/protein"], ["protein/seafood"]),
            (
                ["Entree/protein", "Entree/soup"],
                ["protein/seafood", "cuisine-region/East-Asian"],
            ),
        ],
    )
    @pytest.mark.parametrize("symbol", ["&", "|"])
    def test_get_random_recipe_by_filter(
        recipe_book, recipe_book_builder, categories, tags, symbol
    ):
        filter_str = ""
        if categories:
            filter_str += "c." + f"{symbol} c.".join(categories)
        if tags:
            if filter_str:
                filter_str += " & "
            filter_str += "t." + f"{symbol} t.".join(tags)

        recipe_book.category_tuple = get_lowered_tuple(categories)
        recipe_book.tag_tuple = get_lowered_tuple(tags)

        recipe_book.dataframe = recipe_book_builder.create_recipe(
            categories=recipe_book.category_tuple,
            tags=recipe_book.tag_tuple,
            post_process_recipe=True,
        )
        recipe_book.get_random_recipe_by_filter(filter_str=filter_str)

    @staticmethod
    def test__check_total_time_raises_error_when_nat(
        recipe_book, recipe_book_builder
    ):
        recipe = recipe_book_builder.create_recipe().squeeze()
        recipe.time_total = pd.NaT
        with pytest.raises(RecipeTotalTimeUndefinedError) as error:
            recipe_book._check_total_time(recipe=recipe)
        assert (
            str(error.value)
            == "[recipe total time undefined] recipe=Roasted corn salsa"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "label_type,filter_str",
        [("category", "c.not-a-valid-category"), ("tag", "t.not-a-valid-tag")],
    )
    def test__construct_filter_raises_error(
        recipe_book, label_type, filter_str
    ):
        with pytest.raises(RecipeLabelNotFoundError) as error:
            recipe_book._construct_filter(pd.Series(), filter_str)
        assert str(error.value) == (
            "[recipe label not found] "
            f"field={label_type} "
            f"search_term={filter_str[2:]}"
        )

    @staticmethod
    def test__construct_filter_handles_and(recipe_book, recipe_book_builder):
        tag = "cuisine/italian"
        and_tag = "entree/pasta"
        filter_str = f"t.{tag} & t.{and_tag}"

        recipe_book.category_tuple = tuple(["entree/protein"])
        recipe_book.tag_tuple = tuple([and_tag, tag])

        recipe_base = recipe_book_builder.create_recipe(
            categories=list(recipe_book.category_tuple), tags=[and_tag]
        ).squeeze()
        assert not recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

        recipe_base.tags = [tag, and_tag]
        assert recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

    @staticmethod
    def test__construct_filter_handles_or(recipe_book, recipe_book_builder):
        tag = "cuisine/italian"
        or_tag = "entree/pasta"
        filter_str = f"t.{tag} | t.{or_tag}"

        recipe_book.category_tuple = tuple(["entree/protein"])
        recipe_book.tag_tuple = tuple([or_tag, tag])

        recipe_base = recipe_book_builder.create_recipe(
            categories=list(recipe_book.category_tuple), tags=[or_tag]
        ).squeeze()
        assert recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

        recipe_base.tags = [tag]
        assert recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

    @staticmethod
    def test__construct_filter_handles_not(recipe_book, recipe_book_builder):
        category = "entree/protein"
        tag = "cuisine/italian"
        not_tag = "entree/pasta"
        filter_str = f"c.{category} & t.{tag} & ~t.{not_tag}"

        recipe_book.category_tuple = tuple([category])
        recipe_book.tag_tuple = tuple([not_tag, tag])

        recipe_base = recipe_book_builder.create_recipe(
            categories=[category], tags=[tag, not_tag]
        ).squeeze()
        assert not recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

        recipe_base.tags = [tag]
        assert recipe_book._construct_filter(
            row=recipe_base, filter_str=filter_str
        )

    @staticmethod
    @pytest.mark.parametrize(
        "cell,expected_result",
        [
            (np.nan, []),
            (None, []),
            ([{"title": "Dessert"}], ["dessert"]),
            (
                [{"title": "protein/milk"}, {"title": "cuisine/Brazilian"}],
                ["protein/milk", "cuisine/brazilian"],
            ),
        ],
    )
    def test__flatten_dict_to_list(recipe_book, cell, expected_result):
        assert recipe_book._flatten_dict_to_list(cell) == expected_result

    @staticmethod
    def test__format_recipe_row(recipe_book, recipe_book_builder, log):
        recipe = recipe_book_builder.create_recipe(
            post_process_recipe=False
        ).squeeze()
        expected_recipe = recipe_book_builder.create_recipe(
            uuid_value=recipe.uuid
        ).squeeze()
        assert_equal_series(
            recipe_book._format_recipe_row(recipe), expected_recipe
        )
        assert log.events == [
            {
                "level": "info",
                "event": "[format recipe row]",
                "recipe": "Roasted corn salsa",
            }
        ]

    @staticmethod
    @pytest.mark.parametrize(
        "search_term,expected_result",
        [("found_me", True), ("FOUND_me", True), ("do_not_find_me", False)],
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
            ("get_random_recipe_by_category", "category"),
            ("get_random_recipe_by_tag", "tag"),
        ],
    )
    def test__select_random_recipe_fails_as_label_not_found(
        config_recipe_book,
        recipe_book,
        random_seed,
        recipe_book_builder,
        log,
        method,
        item_type,
    ):
        search_term = "search_term"
        with pytest.raises(RecipeLabelNotFoundError) as error:
            getattr(recipe_book, method)(search_term)
        assert str(error.value) == (
            "[recipe label not found] "
            f"field={item_type} "
            f"search_term={search_term}"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "method,item_type",
        [
            ("get_random_recipe_by_category", "categories"),
            ("get_random_recipe_by_tag", "tags"),
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
        recipe_book.category_tuple = tuple([search_term])
        recipe_book.tag_tuple = tuple([search_term])

        result = getattr(recipe_book, method)(search_term)
        assert_equal_series(result, recipe.squeeze())
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
    @pytest.mark.parametrize(
        "recipe_title,recipe_uuid",
        [["Exclude by menu history", str(uuid.uuid1())]],
    )
    def test__select_random_recipe_weighted_by_rating_removes_exclude_uuid(
        config_recipe_book,
        recipe_book,
        random_seed,
        recipe_book_builder,
        recipe_title,
        recipe_uuid,
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
                # made sure would be selected before excluding
                recipe_book_builder.create_recipe(
                    title=recipe_title,
                    rating=5.0,
                    uuid_value=recipe_uuid,
                    **search_dict,
                ),
                recipe,
            ]
        ).get_recipe_book()
        recipe_book.category_tuple = tuple([search_term])
        recipe_book.tag_tuple = tuple([search_term])

        result = getattr(recipe_book, method)(
            search_term, exclude_uuid_list=[recipe_uuid]
        )
        assert_equal_series(result, recipe.squeeze())

    @staticmethod
    @pytest.mark.parametrize(
        "method,item_type",
        [
            ("get_random_recipe_by_category", "categories"),
            ("get_random_recipe_by_tag", "tags"),
        ],
    )
    @pytest.mark.parametrize(
        "recipe_title,recipe_cooking_time_min",
        [
            ("Excluded by time limit", 35),
            ("Not excluded by time limit", 20),
        ],
    )
    def test__select_random_recipe_weighted_by_rating_removes_long_cooking_time(
        config_recipe_book,
        recipe_book,
        random_seed,
        recipe_book_builder,
        recipe_title,
        recipe_cooking_time_min,
        log,
        method,
        item_type,
    ):
        config_recipe_book.random_select.min_thresh_warning = 5
        max_cook_time = 30

        search_term = "search_term"
        search_dict = {item_type: [search_term]}
        recipe1 = recipe_book_builder.create_recipe(
            title="default one", rating=2.0, **search_dict
        )
        recipe2 = recipe_book_builder.create_recipe(
            title=recipe_title,
            rating=5.0,
            cooking_time_str=f"{recipe_cooking_time_min} min",
            **search_dict,
        )

        recipe_book.dataframe = recipe_book_builder.add_recipe_list(
            [recipe1, recipe2]
        ).get_recipe_book()
        recipe_book.category_tuple = tuple([search_term])
        recipe_book.tag_tuple = tuple([search_term])

        result = getattr(recipe_book, method)(
            search_term, max_cook_active_minutes=max_cook_time
        )
        assert_equal_series(
            result,
            (
                recipe2 if recipe_cooking_time_min <= max_cook_time else recipe1
            ).squeeze(),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "method,item_type",
        [
            ("get_random_recipe_by_category", "categories"),
            ("get_random_recipe_by_tag", "tags"),
            ("get_random_recipe_by_filter", "filter"),
        ],
    )
    @pytest.mark.parametrize(
        "recipe_title,recipe_rating",
        [
            ("Excluded by rating", 2),
            ("Excluded by rating", 0),
            ("Excluded due to no rating", np.nan),
            ("Excluded due to no rating", None),
            ("Not excluded by rating", 5),
        ],
    )
    def test__select_random_recipe_weighted_by_rating_removes_low_rating(
        config_recipe_book,
        recipe_book,
        random_seed,
        recipe_book_builder,
        recipe_title,
        recipe_rating,
        log,
        method,
        item_type,
    ):
        config_recipe_book.random_select.min_thresh_warning = 5
        min_rating = 2.5

        search_term = "search_term"
        search_dict = {item_type: [search_term]}
        if item_type == "filter":
            search_dict = {"tags": [search_term]}

        recipe1 = recipe_book_builder.create_recipe(
            title="default one", rating=2.5, **search_dict
        )
        recipe2 = recipe_book_builder.create_recipe(
            title=recipe_title,
            rating=recipe_rating,
            **search_dict,
        )

        recipe_book.dataframe = recipe_book_builder.add_recipe_list(
            [recipe1, recipe2]
        ).get_recipe_book()
        recipe_book.category_tuple = tuple([search_term])
        recipe_book.tag_tuple = tuple([search_term])

        result = getattr(recipe_book, method)(
            f"t.{search_term}" if item_type == "filter" else search_term,
            min_rating=min_rating,
        )
        assert_equal_series(
            result,
            (
                recipe2
                if (recipe_rating is not None and recipe_rating >= min_rating)
                else recipe1
            ).squeeze(),
        )

    @staticmethod
    def test__select_random_recipe_weighted_by_rating_raise_error(
        recipe_book, recipe_book_builder
    ):
        search_term = "search_term"
        tags = [f"not_{search_term}"]
        recipe_book.dataframe = recipe_book_builder.add_recipe(
            recipe_book_builder.create_recipe(tags=tags)
        ).get_recipe_book()
        recipe_book.category_tuple = tuple([search_term])
        recipe_book.tag_tuple = tuple([search_term])

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


@pytest.mark.parametrize(
    "input_time_string,expected_timedelta",
    [
        ("hurr 30 min", pd.to_timedelta("00:30:00")),
        ("20 min 10 s", pd.to_timedelta("00:20:10")),
        ("0:10", pd.to_timedelta("00:10:00")),
        ("0:10:0", pd.to_timedelta("00:10:00")),
        ("0:10:00", pd.to_timedelta("00:10:00")),
        ("00:10:00", pd.to_timedelta("00:10:00")),
        ("00:10:0", pd.to_timedelta("00:10:00")),
        ("5 hours", pd.to_timedelta("05:00:00")),
        ("15 minutes", pd.to_timedelta("00:15:00")),
        ("5 hours 10 mins", pd.to_timedelta("05:10:00")),
        ("prep time 6 min", pd.to_timedelta("00:06:00")),
    ],
)
def test_create_timedelta(input_time_string, expected_timedelta):
    assert create_timedelta(input_time_string) == expected_timedelta
