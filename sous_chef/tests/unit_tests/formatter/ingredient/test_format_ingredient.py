import pytest
from hydra import compose, initialize
from sous_chef.abstract.search_dataframe import FuzzySearchError
from sous_chef.formatter.format_unit import unit_registry
from sous_chef.formatter.ingredient.format_ingredient import (
    EmptyIngredientError,
    Ingredient,
    IngredientLine,
    PantrySearchError,
    SkipIngredientError,
)
from sous_chef.formatter.ingredient.format_line_abstract import LineParsingError
from sous_chef.formatter.ingredient.format_referenced_recipe import (
    ReferencedRecipe,
)
from tests.unit_tests.formatter.util import create_ingredient_line


@pytest.fixture
def ingredient_line(unit_formatter):
    with initialize(config_path="../../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return lambda line: IngredientLine(
            line=line,
            line_format_dict=config.format_ingredient.ingredient_line_format,
            unit_formatter=unit_formatter,
        )


class TestIngredientLine:
    @staticmethod
    @pytest.mark.parametrize(
        "line,expected_quantity,expected_fraction, expected_item",
        [
            ("avocado", None, None, "avocado"),
            ("1 apple", "1", None, "apple"),
            ("1 cup sugar", "1", None, "cup sugar"),
            ("1/2 tsp vanilla extract", None, "1/2", "tsp vanilla extract"),
            ("1 1/2 cup flour", "1", "1/2", "cup flour"),
            ("4.2 oz. 15% fat cream", "4.2", None, "oz. 15% fat cream"),
            ("1 qt. half-and-half", "1", None, "qt. half-and-half"),
            ("100 g gruyère", "100", None, "g gruyère"),
        ],
    )
    def test__post_init__(
        ingredient_line,
        line,
        expected_quantity,
        expected_fraction,
        expected_item,
    ):
        result = ingredient_line(line)
        assert result.quantity == expected_quantity
        assert result.fraction == expected_fraction
        assert result.item == expected_item

    @staticmethod
    def test__post_init__raises_error_when_not_able_to_parse_line(
        ingredient_line,
    ):
        with pytest.raises(LineParsingError):
            ingredient_line("????")

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
        ingredient_line, str_quantity, str_fraction, expected_float
    ):
        result = ingredient_line("dummy string")
        result.quantity = str_quantity
        result.fraction = str_fraction
        result._set_quantity_float()
        assert result.quantity_float == expected_float

    @staticmethod
    @pytest.mark.parametrize(
        "str_unit_with_item,expected_unit,expected_pint_unit,expected_item",
        [
            ("cup sugar", "cup", unit_registry.cup, "sugar"),
            ("no unit flour", None, None, "no unit flour"),
        ],
    )
    def test__split_item_and_unit(
        ingredient_line,
        str_unit_with_item,
        expected_unit,
        expected_pint_unit,
        expected_item,
    ):
        result = ingredient_line("dummy string")
        result.item = str_unit_with_item
        result._split_item_and_unit()
        assert result.unit == expected_unit
        assert result.pint_unit == expected_pint_unit
        assert result.item == expected_item

    @staticmethod
    @pytest.mark.parametrize(
        "str_item_with_instruction,expected_item,expected_instruction",
        [
            ("no instruction sugar", "no instruction sugar", None),
            ("minced garlic clove", "garlic clove", "minced"),
        ],
    )
    def test__split_item_instruction(
        ingredient_line,
        str_item_with_instruction,
        expected_item,
        expected_instruction,
    ):
        result = ingredient_line("dummy string")
        result.item = str_item_with_instruction
        result._split_item_instruction()
        assert result.item == expected_item
        assert result.instruction == expected_instruction

    @staticmethod
    @pytest.mark.parametrize(
        "line,quantity_float,unit,item",
        [
            ("avocado", 1.0, None, "avocado"),
            ("1 apple", 1.0, None, "apple"),
            ("1 cup sugar", 1.0, "cup", "sugar"),
            ("1/2 tsp vanilla extract", 0.5, "tsp", "vanilla extract"),
            ("1 1/2 cup flour", 1.5, "cup", "flour"),
            ("12.5 ml 15% fat cream", 12.5, "ml", "15% fat cream"),
            ("1 quart half-and-half", 1.0, "qt", "half-and-half"),
            ("100 g gruyère", 100, "g", "gruyère"),
        ],
    )
    def test_convert_to_ingredient(
        ingredient_line, line, quantity_float, unit, item
    ):
        result = ingredient_line(line)
        ingredient = result.convert_to_ingredient()
        pint_unit = unit_registry[unit] if unit is not None else None
        assert ingredient == Ingredient(
            quantity=quantity_float, unit=unit, pint_unit=pint_unit, item=item
        )

    @staticmethod
    def test_convert_to_ingredient_raises_error(ingredient_line):
        result = ingredient_line("1 cup ")
        with pytest.raises(EmptyIngredientError):
            result.convert_to_ingredient()


class TestIngredientFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "ingredient_line,expected_result",
        [
            ("[SAUCE]", True),
            ("[base]", True),
            ("[no ending brace", False),
            ("no starting brace]", False),
            ("not_group", False),
        ],
    )
    def test_is_group(ingredient_formatter, ingredient_line, expected_result):
        assert ingredient_formatter.is_group(ingredient_line) == expected_result

    @staticmethod
    @pytest.mark.parametrize(
        "ingredient_line,expected_result",
        [
            ("[recommended sides]", True),
            ("[SIDES]", True),
            ("[sides]", True),
            ("[optional]", True),
            ("[garnish]", True),
            ("[sauce]", False),
        ],
    )
    def test_is_optional_group(
        ingredient_formatter, ingredient_line, expected_result
    ):
        assert (
            ingredient_formatter.is_optional_group(ingredient_line)
            == expected_result
        )

    @staticmethod
    @pytest.mark.parametrize(
        "raw_ingredient_line,expected_result",
        [
            ("extra spaces end   ", "extra spaces end"),
            ("extra spaces     middle", "extra spaces middle"),
            ("   extra spaces start", "extra spaces start"),
            ("  extra   spaces  everywhere  ", "extra spaces everywhere"),
            ("no extra spaces", "no extra spaces"),
        ],
    )
    def test_strip_line_removes_extra_spaces(
        ingredient_formatter,
        raw_ingredient_line,
        expected_result,
    ):
        assert (
            ingredient_formatter.strip_line(raw_ingredient_line)
            == expected_result
        )

    @staticmethod
    def test_strip_line_ignores_too_small_line(
        ingredient_formatter,
    ):
        assert ingredient_formatter.strip_line("cup") is None

    @staticmethod
    @pytest.mark.parametrize(
        "item,skip",
        [("sugar", "N"), ("eggs", "N")],
    )
    def test__enrich_with_pantry_information(
        ingredient_formatter, mock_pantry_list, pantry_entry, item, skip
    ):
        ingredient = Ingredient(quantity=1, item=item)
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        ingredient_formatter._enrich_with_pantry_detail(ingredient)

        assert ingredient.item == item
        assert not ingredient.is_staple
        assert ingredient.group == pantry_entry.group
        assert ingredient.item_plural == pantry_entry.item_plural
        assert ingredient.store == pantry_entry.store
        assert ingredient.should_skip == (pantry_entry.skip == "Y")

    @staticmethod
    @pytest.mark.parametrize(
        "item,error_arg",
        [
            (
                "not found in pantry",
                FuzzySearchError(
                    field="title",
                    search_term="not found in pantry",
                    result=None,
                    match_quality=0,
                    threshold=95,
                ),
            )
        ],
    )
    def test__enrich_with_pantry_information_raise_pantry_search_error(
        ingredient_formatter, mock_pantry_list, item, error_arg
    ):
        ingredient = Ingredient(quantity=1, item=item)
        mock_pantry_list.retrieve_match.side_effect = error_arg
        with pytest.raises(PantrySearchError):
            ingredient_formatter._enrich_with_pantry_detail(ingredient)

    @staticmethod
    @pytest.mark.parametrize(
        "item,skip",
        [("celery", "Y")],
    )
    def test__enrich_with_pantry_information_raise_skip_ingredient_error(
        ingredient_formatter, mock_pantry_list, pantry_entry, item, skip
    ):
        ingredient = Ingredient(quantity=1, item=item)
        mock_pantry_list.retrieve_match.return_value = pantry_entry
        with pytest.raises(SkipIngredientError):
            ingredient_formatter._enrich_with_pantry_detail(ingredient)

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,skip",
        [
            (
                2.0,
                None,
                "avocado",
                "N",
            ),
            (1.0, "cup", "sugar", "N"),
        ],
    )
    def test_format_ingredient_line(
        ingredient_formatter,
        mock_pantry_list,
        pantry_entry,
        quantity,
        unit,
        item,
    ):
        pint_unit = unit_registry[unit] if unit is not None else None
        line_str = create_ingredient_line(item, quantity, unit)
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        expected_ingredient = Ingredient(
            quantity=quantity, unit=unit, pint_unit=pint_unit, item=item
        )
        expected_ingredient.set_pantry_info(pantry_entry)
        assert (
            ingredient_formatter.format_ingredient_line(line_str)
            == expected_ingredient
        )

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,skip",
        [
            (1, "cup", "rice", "N"),
            (0.5, "head", "salad", "N"),
        ],
    )
    def test_format_manual_ingredient(
        ingredient_formatter,
        mock_pantry_list,
        pantry_entry,
        quantity,
        unit,
        item,
        skip,
    ):
        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        mock_pantry_list.retrieve_match.return_value = pantry_entry

        ingredient.set_pantry_info(pantry_entry)
        assert (
            ingredient_formatter.format_manual_ingredient(quantity, unit, item)
            == ingredient
        )

    @staticmethod
    @pytest.mark.parametrize(
        "line,quantity_float,title",
        [
            ("# garlic aioli", 1, "garlic aioli"),
            ("# 0.5 baguette", 0.5, "baguette"),
            ("# 1 cup french onion soup", 1, "french onion soup"),
            # recipe factor with unit not yet implemented
            ("# 2 cups salsa brava", 1, "salsa brava"),
        ],
    )
    def test_format_referenced_recipe(
        ingredient_formatter, line, quantity_float, title
    ):
        assert ingredient_formatter.format_referenced_recipe(
            line
        ) == ReferencedRecipe(quantity=quantity_float, title=title)
