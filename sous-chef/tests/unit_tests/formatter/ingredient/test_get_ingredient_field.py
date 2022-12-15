import pytest
from hydra import compose, initialize
from omegaconf import OmegaConf
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from structlog import get_logger
from tests.unit_tests.formatter.util import create_ingredient_line
from tests.unit_tests.util import create_recipe
from tests.util import assert_equal_series

FILE_LOGGER = get_logger(__name__)


@pytest.fixture
def ingredient_field(ingredient_formatter, mock_recipe_book):
    with initialize(
        version_base=None, config_path="../../../../config/formatter"
    ):
        config = compose(config_name="get_ingredient_field")
        return IngredientField(
            ingredient_formatter=ingredient_formatter,
            config=config.get_ingredient_field,
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


class TestIngredientFieldFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,factor,recipe_title",
        [(2.5, "tbsp", "sugar", 0.25, "garlic aioli")],
    )
    def test_parse_ingredient_field(
        ingredient_field,
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
        ingredient_str = create_ingredient_line(item, quantity, unit)
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        (
            recipe_list,
            ingredient_list,
            error_list,
        ) = ingredient_field.parse_ingredient_field(
            ingredient_field=f"{recipe_str}\n{ingredient_str}"
        )
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
        ingredient_field,
        mock_pantry_list,
        pantry_entry,
        quantity,
        unit,
        item,
    ):
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        (
            recipe_list,
            ingredient_list,
            error_list,
        ) = ingredient_field.parse_ingredient_field(
            f"[garnish]\n{create_ingredient_line(item, quantity, unit)}"
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
        ingredient_field,
        mock_recipe_book,
        factor,
        unit,
        recipe_title,
    ):
        line_str = "# " + create_ingredient_line(
            quantity=factor, unit=unit, item=recipe_title
        )
        recipe_with_recipe_title = create_recipe(title=recipe_title)

        ingredient_field.referenced_recipe_list = []
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        ingredient_field._format_referenced_recipe(line_str)
        result = ingredient_field.referenced_recipe_list
        assert_recipe(
            result, recipe_with_recipe_title, factor=factor, amount=line_str
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item,quantity,unit,is_in_optional_group",
        [("rice", 1.0, "cup", False), ("avocado", 2.0, None, False)],
    )
    def test__format_ingredient(
        ingredient_field,
        mock_pantry_list,
        pantry_entry,
        item,
        quantity,
        unit,
        is_in_optional_group,
    ):
        line_str = create_ingredient_line(item, quantity, unit)
        ingredient_field.ingredient_list = []
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        ingredient_field._format_ingredient(line_str, is_in_optional_group)
        result = ingredient_field.ingredient_list
        assert_ingredient(
            result,
            pantry_entry,
            quantity,
            unit,
            item,
            is_in_optional_group,
            factor=1.0,
        )
