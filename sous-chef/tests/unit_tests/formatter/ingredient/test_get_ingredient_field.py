import pytest
from hydra import compose, initialize
from omegaconf import OmegaConf
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.get_ingredient_field import (
    IngredientField,
    ReferencedRecipeDimensionalityError,
)
from structlog import get_logger
from tests.unit_tests.formatter.util import create_ingredient_line
from tests.unit_tests.util import create_recipe

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
    result,
    pantry_entry,
    quantity,
    pint_unit,
    item,
    is_in_optional_group,
    factor=1.0,
):
    assert result == [
        Ingredient(
            quantity=quantity,
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


def assert_recipe(result, ref_recipe, factor: float, amount: str):
    tmp_ref_recipe = ref_recipe.copy(deep=True)
    tmp_ref_recipe.factor = factor
    tmp_ref_recipe.amount = amount
    assert tuple(result.items()) == tuple(tmp_ref_recipe.items())


class TestIngredientFieldFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item,factor,recipe_title",
        [(2.5, unit_registry.tablespoon, "sugar", 0.25, "garlic aioli")],
    )
    def test_parse_ingredient_field(
        ingredient_field,
        mock_pantry_list,
        mock_recipe_book,
        pantry_entry,
        quantity,
        pint_unit,
        item,
        factor,
        recipe_title,
    ):
        recipe_str = "# " + create_ingredient_line(
            quantity=factor, item=recipe_title
        )
        ingredient_str = create_ingredient_line(item, quantity, pint_unit)
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title.copy(deep=True)
        )

        (
            recipe_list,
            ingredient_list,
            error_list,
        ) = ingredient_field.parse_ingredient_field(
            create_recipe(ingredients=f"{recipe_str}\n{ingredient_str}")
        )

        assert_recipe(
            recipe_list[0], recipe_with_recipe_title, factor, recipe_str
        )
        assert_ingredient(
            ingredient_list,
            pantry_entry,
            quantity,
            pint_unit,
            item,
            is_in_optional_group=False,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item", [(1.25, unit_registry.cups, "flour")]
    )
    def test_parse_ingredient_field_in_optional_group(
        ingredient_field,
        mock_pantry_list,
        pantry_entry,
        quantity,
        pint_unit,
        item,
    ):
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        ingredients = (
            f"[garnish]\n{create_ingredient_line(item, quantity, pint_unit)}"
        )

        (
            recipe_list,
            ingredient_list,
            error_list,
        ) = ingredient_field.parse_ingredient_field(
            create_recipe(ingredients=ingredients)
        )

        assert recipe_list == []
        assert_ingredient(
            ingredient_list,
            pantry_entry,
            quantity,
            pint_unit,
            item,
            is_in_optional_group=True,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item,quantity,pint_unit,is_in_optional_group",
        [
            ("rice", 1.0, unit_registry.cup, False),
            ("avocado", 2.0, unit_registry.dimensionless, False),
        ],
    )
    def test__format_ingredient(
        ingredient_field,
        mock_pantry_list,
        pantry_entry,
        item,
        quantity,
        pint_unit,
        is_in_optional_group,
    ):
        line_str = create_ingredient_line(item, quantity, pint_unit)
        ingredient_field.ingredient_list = []
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        ingredient_field._format_ingredient(line_str, is_in_optional_group)
        result = ingredient_field.ingredient_list
        assert_ingredient(
            result,
            pantry_entry,
            quantity,
            pint_unit,
            item,
            is_in_optional_group,
            factor=1.0,
        )


class TestFormatReferencedRecipe:
    @staticmethod
    @pytest.mark.parametrize(
        "needed_factor,ref_pint_repr",
        [
            pytest.param(1, 0.5 * unit_registry.cup, id="cup"),
            pytest.param(8, 1 * unit_registry.tablespoon, id="tbsp"),
        ],
    )
    def test_with_dimensionless_works(
        ingredient_field,
        mock_recipe_book,
        needed_factor,
        ref_pint_repr,
    ):
        ref_recipe_title = "patatas bravas"
        ref_recipe = create_recipe(
            title=f"{ref_recipe_title}", pint_quantity=ref_pint_repr
        )
        # set up mocks
        ingredient_field.referenced_recipe_list = []
        mock_recipe_book.get_recipe_by_title.return_value = ref_recipe.copy(
            deep=True
        )
        # create base recipe ingredient line
        line_str = f"# {needed_factor} {ref_recipe_title}"

        ingredient_field._format_referenced_recipe(
            source_recipe_title="dummy", line=line_str
        )

        assert_recipe(
            result=ingredient_field.referenced_recipe_list[0],
            ref_recipe=ref_recipe,
            factor=needed_factor,
            amount=line_str,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "needed_ref_pint_repr,ref_pint_repr,expected_factor",
        [
            pytest.param(
                1 * unit_registry.cup,
                0.5 * unit_registry.cup,
                2,
                id="both_cups",
            ),
            pytest.param(
                8 * unit_registry.tablespoon,
                1 * unit_registry.cup,
                0.5,
                id="tbsp_cup",
            ),
        ],
    )
    def test_with_same_dimensionality_works(
        ingredient_field,
        mock_recipe_book,
        needed_ref_pint_repr,
        ref_pint_repr,
        expected_factor,
    ):
        ref_recipe_title = "patatas bravas"
        ref_recipe = create_recipe(
            title=f"{ref_recipe_title}", pint_quantity=ref_pint_repr
        )
        # set up mocks
        ingredient_field.referenced_recipe_list = []
        mock_recipe_book.get_recipe_by_title.return_value = ref_recipe.copy(
            deep=True
        )
        # create base recipe ingredient line
        line_str = f"# {needed_ref_pint_repr} {ref_recipe_title}"

        ingredient_field._format_referenced_recipe(
            source_recipe_title="dummy", line=line_str
        )

        assert_recipe(
            result=ingredient_field.referenced_recipe_list[0],
            ref_recipe=ref_recipe,
            factor=expected_factor,
            amount=line_str,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "needed_ref_pint_repr,ref_pint_repr",
        [
            pytest.param(
                1 * unit_registry.cup,
                0.5 * unit_registry.dimensionless,
                id="cup_dimensionless",
            ),
            pytest.param(
                8 * unit_registry.tablespoon, 1 * unit_registry.g, id="tbsp_g"
            ),
        ],
    )
    def test_with_different_dimensionality_raises_error(
        ingredient_field, mock_recipe_book, needed_ref_pint_repr, ref_pint_repr
    ):
        ref_recipe_title = "patatas bravas"
        ref_recipe = create_recipe(
            title=f"{ref_recipe_title}", pint_quantity=ref_pint_repr
        )
        # set up mocks
        ingredient_field.referenced_recipe_list = []
        mock_recipe_book.get_recipe_by_title.return_value = ref_recipe.copy(
            deep=True
        )

        with pytest.raises(ReferencedRecipeDimensionalityError):
            ingredient_field._format_referenced_recipe(
                source_recipe_title="dummy",
                line=f"# {needed_ref_pint_repr} {ref_recipe_title}",
            )
