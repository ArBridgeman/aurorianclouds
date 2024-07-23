import pytest
from sous_chef.formatter.format_unit import UnitExtractionError, unit_registry


class TestUnitFormatter:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,desired_pint_unit,expected_quantity,expected_unit",
        [
            (3, unit_registry.tsp, unit_registry.tbsp, 1, "tbsp"),
            (4, unit_registry.tbsp, unit_registry.cup, 0.25, "cup"),
            (400, unit_registry.gram, unit_registry.kg, 0.4, "kg"),
            (16, unit_registry.ounce, unit_registry.g, 453.59, "g"),
        ],
    )
    def test_convert_to_desired_unit(
        unit_formatter,
        quantity,
        pint_unit,
        desired_pint_unit,
        expected_quantity,
        expected_unit,
    ):
        assert unit_formatter.convert_to_desired_unit(
            quantity, pint_unit, desired_pint_unit
        ) == (expected_quantity, expected_unit, desired_pint_unit)

    @staticmethod
    @pytest.mark.parametrize(
        "text,expected_pint_unit",
        [
            ("", unit_registry.dimensionless),
            ("cp", unit_registry.cup),
            ("cp.", unit_registry.cup),
            ("cup", unit_registry.cup),
            ("cups", unit_registry.cup),
            ("ball", unit_registry.ball),
            ("pinches", unit_registry.pinch),
        ],
    )
    def test_get_pint_unit(unit_formatter, text, expected_pint_unit):
        assert unit_formatter.get_pint_unit(text) == expected_pint_unit

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,expected_str",
        [
            (1, unit_registry.cup, "cup"),
            (2, unit_registry.cup, "cups"),
            (1, unit_registry.tablespoon, "tbsp"),
            (2, unit_registry.tablespoon, "tbsp"),
            (1, unit_registry.slice, "slice"),
            (2, unit_registry.slice, "slices"),
            (1, unit_registry.pinch, "pinch"),
            # TODO not implemented correctly
            (2, unit_registry.pinch, "pinchs"),
        ],
    )
    def test_get_unit_str(unit_formatter, quantity, unit, expected_str):
        assert unit_formatter.get_unit_str(quantity, unit) == expected_str

    @staticmethod
    def test_get_pint_unit_raise_error_for_not_unit(unit_formatter, log):
        with pytest.raises(UnitExtractionError) as error:
            unit_formatter.get_pint_unit("not-a-unit")

        assert log.events == []
        assert str(error.value) == "[unit extraction failed] text=not-a-unit"

    @staticmethod
    def test_get_pint_unit_raise_error_for_not_allowed_unit(
        unit_formatter, log
    ):
        with pytest.raises(UnitExtractionError) as error:
            unit_formatter.get_pint_unit("mile")

        assert log.events == [
            {
                "event": "[get pint unit]",
                "level": "warning",
                "warn": "unit not in allowed_unit_list",
                "unit": unit_registry.mile,
            }
        ]
        assert str(error.value) == "[unit extraction failed] text=mile"

    @staticmethod
    @pytest.mark.parametrize(
        "text_unit,expected_unit",
        [
            ("cm", unit_registry.centimeter),
            ("g", unit_registry.gram),
            ("in", unit_registry.inch),
        ],
    )
    def test_get_pint_unit_parses_abbreviated_unit(
        unit_formatter, text_unit, expected_unit
    ):
        assert unit_formatter.get_pint_unit(text_unit) == expected_unit

    @staticmethod
    @pytest.mark.parametrize(
        "text_unit,expected_unit",
        [
            ("centimeter", unit_registry.centimeter),
            ("cup", unit_registry.cup),
            ("gram", unit_registry.gram),
        ],
    )
    def test_get_pint_unit_parses_singular_unit(
        unit_formatter, text_unit, expected_unit
    ):
        assert unit_formatter.get_pint_unit(text_unit) == expected_unit

    @staticmethod
    @pytest.mark.parametrize(
        "text_unit,expected_unit",
        [
            ("centimeters", unit_registry.centimeter),
            ("tablespoons", unit_registry.tablespoon),
        ],
    )
    def test_get_pint_unit_parses_plural_unit(
        unit_formatter, text_unit, expected_unit
    ):
        assert unit_formatter.get_pint_unit(text_unit) == expected_unit

    @staticmethod
    @pytest.mark.parametrize(
        "text_unit,expected_unit",
        [
            ("Tbsps", unit_registry.tablespoon),
            ("Tablespoons", unit_registry.tablespoon),
        ],
    )
    def test_get_pint_unit_parses_upper_case_unit(
        unit_formatter, text_unit, expected_unit
    ):
        assert unit_formatter.get_pint_unit(text_unit) == expected_unit

    @staticmethod
    @pytest.mark.parametrize(
        "unit, expected_result",
        [
            (unit_registry.centimeter, "cm"),
            (unit_registry.cup, "cup"),
            (unit_registry.gram, "g"),
            (unit_registry.ball, "ball"),
        ],
    )
    def test_get_unit_as_abbreviated_str(unit_formatter, unit, expected_result):
        assert (
            unit_formatter.get_unit_as_abbreviated_str(unit) == expected_result
        )
