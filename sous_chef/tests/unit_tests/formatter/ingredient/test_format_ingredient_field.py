import pytest
from hydra import compose, initialize
from omegaconf import OmegaConf
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_ingredient import (
    EmptyIngredientError,
    Ingredient,
    PantrySearchError,
    SkipIngredientError,
)
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
    raise_or_log_exception,
)
from sous_chef.recipe_book.read_recipe_book import Recipe
from structlog import get_logger
from tests.unit_tests.formatter.util import create_ingredient_line

FILE_LOGGER = get_logger(__name__)


def setup_ingredient_field_formatter(ingredient_formatter, recipe_book):
    with initialize(config_path="../../../../config/formatter"):
        config = compose(config_name="format_ingredient_field")
        return IngredientFieldFormatter(
            ingredient_formatter=ingredient_formatter,
            config=config,
            recipe_book=recipe_book,
        )


@pytest.fixture
def ingredient_field_formatter(ingredient_formatter, mock_recipe_book):
    return setup_ingredient_field_formatter(
        ingredient_formatter, mock_recipe_book
    )


@pytest.fixture
def ingredient_field_formatter_find_pantry_entry(
    ingredient_formatter_find_pantry_entry, mock_recipe_book
):
    return setup_ingredient_field_formatter(
        ingredient_formatter_find_pantry_entry, mock_recipe_book
    )


@pytest.fixture
def ingredient_field_formatter_find_recipe(
    ingredient_formatter, mock_recipe_book, recipe_with_recipe_title
):
    mock_recipe_book.get_recipe_by_title.return_value = recipe_with_recipe_title
    return setup_ingredient_field_formatter(
        ingredient_formatter, mock_recipe_book
    )


@pytest.fixture
def ingredient_field_formatter_complete(
    ingredient_formatter_find_pantry_entry,
    mock_recipe_book,
    recipe_with_recipe_title,
):
    mock_recipe_book.get_recipe_by_title.return_value = recipe_with_recipe_title
    return setup_ingredient_field_formatter(
        ingredient_formatter_find_pantry_entry, mock_recipe_book
    )


def create_error_config(raise_error_for: bool, still_add_ingredient: bool):
    return OmegaConf.create(
        {
            "raise_error_for": raise_error_for,
            "still_add_ingredient": still_add_ingredient,
        }
    )


def assert_ingredient(
    result, pantry_entry, quantity, unit, item, is_in_optional_group, factor=1.0
):
    pint_unit = unit_registry[unit] if unit is not None else None
    assert result == [
        Ingredient(
            quantity=quantity,
            unit=unit,
            item=item,
            pint_unit=pint_unit,
            factor=factor,
            is_optional=is_in_optional_group,
            is_staple=pantry_entry.is_staple,
            group=pantry_entry.group,
            item_plural=pantry_entry.item_plural,
            store=pantry_entry.store,
            should_skip=(pantry_entry.skip == "Y"),
        )
    ]


def assert_recipe(result, recipe, factor):
    assert result == [
        Recipe(
            title=recipe.title,
            rating=recipe.rating,
            total_cook_time=recipe.total_cook_time,
            ingredient_field=recipe.ingredient_field,
            factor=factor,
        )
    ]


def test_raise_or_log_exception_raise_exception():
    with pytest.raises(Exception):
        raise_or_log_exception(raise_exception=True, exception=Exception())


def test_raise_or_log_exception_log_exception(log):
    raise_or_log_exception(raise_exception=False, exception=Exception())
    assert log.events == [{"event": "", "level": "error"}]


class TestIngredientFieldFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,skip,factor,recipe_title",
        [(2.5, "tbsp", "sugar", "N", 0.25, "garlic aioli")],
    )
    def test_parse_ingredient_field(
        ingredient_field_formatter_complete,
        recipe_with_recipe_title,
        pantry_entry,
        quantity,
        unit,
        item,
        skip,
        factor,
        recipe_title,
    ):
        recipe_str = "# " + create_ingredient_line(
            quantity=factor, item=recipe_title
        )
        ingredient_str = create_ingredient_line(item, quantity, unit)
        ingredient_field = f"{recipe_str}\n{ingredient_str}"

        (
            recipe_list,
            ingredient_list,
        ) = ingredient_field_formatter_complete.parse_ingredient_field(
            ingredient_field
        )
        assert_recipe(recipe_list, recipe_with_recipe_title, factor)
        assert_ingredient(
            ingredient_list,
            pantry_entry,
            quantity,
            unit,
            item,
            is_in_optional_group=False,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,skip", [(1.25, "cup", "flour", "N")]
    )
    def test_parse_ingredient_field_in_optional_group(
        ingredient_field_formatter_find_pantry_entry,
        pantry_entry,
        quantity,
        unit,
        item,
        skip,
    ):
        ingredient_str = create_ingredient_line(item, quantity, unit)
        ingredient_field = f"[garnish]\n{ingredient_str}"

        (
            recipe_list,
            ingredient_list,
        ) = ingredient_field_formatter_find_pantry_entry.parse_ingredient_field(
            ingredient_field
        )
        assert recipe_list == []
        assert_ingredient(
            ingredient_list,
            pantry_entry,
            quantity,
            unit,
            item,
            is_in_optional_group=True,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "factor,unit,recipe_title", [(0.5, None, "patatas bravas")]
    )
    def test__format_referenced_recipe_to_recipe(
        ingredient_field_formatter_find_recipe,
        recipe_with_recipe_title,
        factor,
        unit,
        recipe_title,
    ):
        line_str = "# " + create_ingredient_line(
            quantity=factor, unit=unit, item=recipe_title
        )
        ingredient_field_formatter_find_recipe.referenced_recipe_list = []
        ingredient_field_formatter_find_recipe._format_referenced_recipe(
            line_str
        )
        result = ingredient_field_formatter_find_recipe.referenced_recipe_list
        assert_recipe(result, recipe_with_recipe_title, factor=factor)

    @staticmethod
    @pytest.mark.parametrize(
        "item,quantity,unit,is_in_optional_group,skip",
        [("rice", 1.0, "cup", False, "N"), ("avocado", 2.0, None, False, "N")],
    )
    def test__format_ingredient(
        ingredient_field_formatter_find_pantry_entry,
        pantry_entry,
        item,
        quantity,
        unit,
        is_in_optional_group,
        skip,
    ):
        line_str = create_ingredient_line(item, quantity, unit)
        ingredient_field_formatter_find_pantry_entry.ingredient_list = []

        ingredient_field_formatter_find_pantry_entry._format_ingredient(
            line_str, is_in_optional_group
        )
        result = ingredient_field_formatter_find_pantry_entry.ingredient_list
        assert_ingredient(
            result,
            pantry_entry,
            quantity,
            unit,
            item,
            is_in_optional_group,
            factor=1.0,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "error",
        [EmptyIngredientError, PantrySearchError, SkipIngredientError],
    )
    def test__handle_ingredient_exception_raise_error(
        ingredient_field_formatter, error
    ):
        config = create_error_config(
            raise_error_for=True, still_add_ingredient=False
        )
        ingredient = Ingredient(quantity=1, item="dummy ingredient")
        raised_error = error(ingredient)
        ingredient_field_formatter.ingredient_list = []

        with pytest.raises(error):
            ingredient_field_formatter._handle_ingredient_exception(
                config, raised_error
            )

        assert ingredient_field_formatter.ingredient_list == []

    @staticmethod
    @pytest.mark.parametrize(
        "error",
        [EmptyIngredientError, PantrySearchError, SkipIngredientError],
    )
    def test__handle_ingredient_exception_as_warning_ignore_ingredient(
        ingredient_field_formatter, log, error
    ):
        config = create_error_config(
            raise_error_for=False, still_add_ingredient=False
        )
        ingredient = Ingredient(quantity=1, item="dummy ingredient")
        raised_error = error(ingredient)
        ingredient_field_formatter.ingredient_list = []

        ingredient_field_formatter._handle_ingredient_exception(
            config, raised_error
        )
        assert log.events == [
            {
                "event": f"{raised_error.message} ingredient={ingredient.item}",
                "level": "error",
            }
        ]
        assert ingredient_field_formatter.ingredient_list == []

    @staticmethod
    @pytest.mark.parametrize(
        "error",
        [EmptyIngredientError, PantrySearchError, SkipIngredientError],
    )
    def test__handle_ingredient_exception_as_warning_still_add_to_list(
        ingredient_field_formatter, log, error
    ):
        config = create_error_config(
            raise_error_for=False, still_add_ingredient=True
        )
        ingredient = Ingredient(quantity=1, item="dummy ingredient")
        raised_error = error(ingredient)
        ingredient_field_formatter.ingredient_list = []

        ingredient_field_formatter._handle_ingredient_exception(
            config, raised_error
        )
        assert log.events[0] == {
            "event": f"{raised_error.message} ingredient={ingredient.item}",
            "level": "error",
        }
        assert log.events[1] == {
            "event": "[ignore error]",
            "action": "still add to list",
            "ingredient": ingredient.item,
            "level": "warning",
        }
        assert ingredient_field_formatter.ingredient_list == [ingredient]
