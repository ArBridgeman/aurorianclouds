import copy
from unittest.mock import patch

from sous_chef.nutrition.provide_nutritional_info import Product

# Mirrors the OpenFoodFacts API response shape used by _extract_per_product.
# Keys follow the field mapping logic in _extract_fields (prefix removal /
# suffix addition / underscore → hyphen replacement for special fields).
MOCK_OFF_RESPONSE = {
    "status_verbose": "product found",
    "product": {
        "product_name": "Ricotta 45% Fett i.Tr.",
        "quantity": "250g",
        "brands": "Edeka",
        "completeness": 0.7875,
        "nutriscore_grade": "c",
        "nutrient_levels": {
            "fat": "moderate",
            "salt": "moderate",
            "saturated-fat": "high",
            "sugars": "low",
        },
        "nutriments": {
            "carbohydrates_100g": 4.5,
            "energy-kcal_100g": 181.0,
            "fat_100g": 14.0,
            "fiber_100g": None,
            "proteins_100g": 9.2,
            "salt_100g": 0.3,
            "saturated-fat_100g": 9.3,
            "sugars_100g": 4.5,
        },
    },
}


class TestNutritionist:
    @staticmethod
    def test__extract_per_product(nutritionist):
        with patch(
            "openfoodfacts.products.get_product",
            side_effect=lambda _: copy.deepcopy(MOCK_OFF_RESPONSE),
        ):
            product = nutritionist._extract_per_product(
                "4311501619810",
                group="Dairy force",
                pantry_ingredient="ricotta",
            )
        assert product == Product(
            brands="Edeka",
            barcode="'4311501619810",
            group="Dairy force",
            pantry_ingredient="ricotta",
            completeness=0.7875,
            nutriscore_grade="c",
            product_name="Ricotta 45% Fett i.Tr.",
            quantity="250g",
            level_fat="moderate",
            level_salt="moderate",
            level_saturated_fat="high",
            level_sugars="low",
            per_100g_carbohydrates=4.5,
            per_100g_energy_kcal=181.0,
            per_100g_fat=14.0,
            per_100g_proteins=9.2,
            per_100g_salt=0.3,
            per_100g_saturated_fat=9.3,
            per_100g_sugars=4.5,
        )
