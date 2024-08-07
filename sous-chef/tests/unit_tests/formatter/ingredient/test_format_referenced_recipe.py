import pytest
from hydra import compose, initialize
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_line_abstract import LineParsingError
from sous_chef.formatter.ingredient.format_referenced_recipe import (
    NoTitleReferencedRecipeError,
    ReferencedRecipe,
    ReferencedRecipeLine,
)


@pytest.fixture
def referenced_recipe_line(unit_formatter):
    with initialize(
        version_base=None, config_path="../../../../config/formatter"
    ):
        config = compose(config_name="format_ingredient")
        return lambda line: ReferencedRecipeLine(
            line=line,
            line_format_dict=config.format_ingredient.referenced_recipe_format,
            unit_formatter=unit_formatter,
        )


class TestReferencedRecipeLine:
    @staticmethod
    @pytest.mark.parametrize(
        "line,expected_quantity, expected_item",
        [
            ("# crepe dough", None, "crepe dough"),
            ("# 0.5 garlic aioli", "0.5", "garlic aioli"),
            ("# 1 cup salsa brava", "1", "cup salsa brava"),
        ],
    )
    def test__post_init__(
        referenced_recipe_line,
        line,
        expected_quantity,
        expected_item,
    ):
        result = referenced_recipe_line(line)
        assert result.quantity == expected_quantity
        assert result.item == expected_item

    @staticmethod
    def test__post_init__raises_error_when_not_able_to_parse_line(
        referenced_recipe_line,
    ):
        with pytest.raises(LineParsingError):
            referenced_recipe_line("????")

    @staticmethod
    @pytest.mark.parametrize(
        "str_quantity,str_fraction, expected_float",
        [
            (None, None, 1),
            ("1", None, 1),
            (None, "1/2", 0.5),
            ("1", "1/2", 1.5),
            ("4.2", None, 4.2),
        ],
    )
    def test__set_quantity_float(
        referenced_recipe_line, str_quantity, str_fraction, expected_float
    ):
        result = referenced_recipe_line("# dummy string")
        result.quantity = str_quantity
        result.fraction = str_fraction
        result._set_quantity_float()
        assert result.quantity_float == expected_float

    @staticmethod
    @pytest.mark.parametrize(
        "str_unit_with_item,expected_pint_unit,expected_item",
        [
            ("cup salsa brava", unit_registry.cup, "salsa brava"),
            (
                "no unit garlic aioli",
                unit_registry.dimensionless,
                "no unit garlic aioli",
            ),
        ],
    )
    def test__split_item_and_unit(
        referenced_recipe_line,
        str_unit_with_item,
        expected_pint_unit,
        expected_item,
    ):
        result = referenced_recipe_line("# dummy string")
        result.item = str_unit_with_item
        result._split_item_and_unit()
        assert result.pint_unit == expected_pint_unit
        assert result.item == expected_item

    @staticmethod
    @pytest.mark.parametrize(
        "line,quantity,pint_unit,title",
        [
            (
                "# garlic aioli",
                1.0,
                unit_registry.dimensionless,
                "garlic aioli",
            ),
            (
                "# 2 salsa brava",
                2.0,
                unit_registry.dimensionless,
                "salsa brava",
            ),
            ("# 2 cups salsa brava", 2.0, unit_registry.cup, "salsa brava"),
        ],
    )
    def test_convert_to_referenced_recipe(
        referenced_recipe_line, line, quantity, pint_unit, title
    ):
        result = referenced_recipe_line(line)
        referenced_recipe = result.convert_to_referenced_recipe()
        assert referenced_recipe == ReferencedRecipe(
            quantity=quantity, pint_unit=pint_unit, title=title, amount=line
        )

    @staticmethod
    def test_convert_to_referenced_recipe_raise_error(referenced_recipe_line):
        result = referenced_recipe_line("# 1 cup ")
        with pytest.raises(NoTitleReferencedRecipeError) as error:
            result.convert_to_referenced_recipe()
        assert str(error.value) == "[empty title] referenced_recipe="
