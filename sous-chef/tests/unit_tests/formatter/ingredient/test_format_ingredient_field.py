import pytest
from hydra import compose, initialize
from omegaconf import OmegaConf
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_ingredient import (
    EmptyIngredientError,
    Ingredient,
    PantrySearchError,
)
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
    raise_or_log_exception,
)
from structlog import get_logger
from tests.unit_tests.formatter.util import create_ingredient_line
from tests.unit_tests.util import create_recipe
from tests.util import assert_equal_series

FILE_LOGGER = get_logger(__name__)


@pytest.fixture
def ingredient_field_formatter(ingredient_formatter, mock_recipe_book):
    with initialize(
        version_base=None, config_path="../../../../config/formatter"
    ):
        config = compose(config_name="format_ingredient_field")
        return IngredientFieldFormatter(
            ingredient_formatter=ingredient_formatter,
            config=config,
            recipe_book=mock_recipe_book,
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
            barcode=pantry_entry.barcode,
            recipe_uuid=pantry_entry.recipe_uuid,
        )
    ]


def assert_recipe(result, recipe, factor: float, amount: str = None):
    assert_equal_series(
        result[0],
        create_recipe(
            title=recipe.title,
            rating=recipe.rating,
            time_total_str=str(recipe.time_total),
            ingredients=recipe.ingredients,
            factor=factor,
            amount=amount,
        ),
    )


def test_raise_or_log_exception_raise_exception():
    with pytest.raises(Exception):
        raise_or_log_exception(raise_exception=True, exception=Exception())


def test_raise_or_log_exception_log_exception(log):
    raise_or_log_exception(raise_exception=False, exception=Exception())
    assert log.events == [{"event": "", "level": "error"}]


class TestIngredientFieldFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,factor,recipe_title",
        [(2.5, "tbsp", "sugar", 0.25, "garlic aioli")],
    )
    def test_parse_ingredient_field(
        ingredient_field_formatter,
        mock_pantry_list,
        mock_recipe_book,
        pantry_entry,
        quantity,
        unit,
        item,
        factor,
        recipe_title,
    ):
        recipe_str = "# " + create_ingredient_line(
            quantity=factor, item=recipe_title
        )
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        ingredient_str = create_ingredient_line(item, quantity, unit)
        ingredient_field = f"{recipe_str}\n{ingredient_str}"
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        (
            recipe_list,
            ingredient_list,
        ) = ingredient_field_formatter.parse_ingredient_field(ingredient_field)
        assert_recipe(recipe_list, recipe_with_recipe_title, factor, recipe_str)
        assert_ingredient(
            ingredient_list,
            pantry_entry,
            quantity,
            unit,
            item,
            is_in_optional_group=False,
        )

    @staticmethod
    @pytest.mark.parametrize("quantity,unit,item", [(1.25, "cup", "flour")])
    def test_parse_ingredient_field_in_optional_group(
        ingredient_field_formatter,
        mock_pantry_list,
        pantry_entry,
        quantity,
        unit,
        item,
    ):
        ingredient_str = create_ingredient_line(item, quantity, unit)
        ingredient_field = f"[garnish]\n{ingredient_str}"
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        (
            recipe_list,
            ingredient_list,
        ) = ingredient_field_formatter.parse_ingredient_field(ingredient_field)

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
        ingredient_field_formatter,
        mock_recipe_book,
        factor,
        unit,
        recipe_title,
    ):
        line_str = "# " + create_ingredient_line(
            quantity=factor, unit=unit, item=recipe_title
        )
        recipe_with_recipe_title = create_recipe(title=recipe_title)

        ingredient_field_formatter.referenced_recipe_list = []
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        ingredient_field_formatter._format_referenced_recipe(line_str)
        result = ingredient_field_formatter.referenced_recipe_list
        assert_recipe(
            result, recipe_with_recipe_title, factor=factor, amount=line_str
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item,quantity,unit,is_in_optional_group",
        [("rice", 1.0, "cup", False), ("avocado", 2.0, None, False)],
    )
    def test__format_ingredient(
        ingredient_field_formatter,
        mock_pantry_list,
        pantry_entry,
        item,
        quantity,
        unit,
        is_in_optional_group,
    ):
        line_str = create_ingredient_line(item, quantity, unit)
        ingredient_field_formatter.ingredient_list = []
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        ingredient_field_formatter._format_ingredient(
            line_str, is_in_optional_group
        )
        result = ingredient_field_formatter.ingredient_list
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
        [EmptyIngredientError, PantrySearchError],
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
        [EmptyIngredientError, PantrySearchError],
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
        [EmptyIngredientError, PantrySearchError],
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
