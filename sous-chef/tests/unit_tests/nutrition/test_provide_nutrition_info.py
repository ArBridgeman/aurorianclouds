from sous_chef.nutrition.provide_nutritional_info import Product


class TestNutritionist:
    @staticmethod
    def test__extract_per_product(nutritionist):
        product = nutritionist._extract_per_product(
            "4311501619810", group="Dairy force", pantry_ingredient="ricotta"
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
