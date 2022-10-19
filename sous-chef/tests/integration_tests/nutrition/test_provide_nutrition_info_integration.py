class TestNutritionist:
    @staticmethod
    def test_sync_pantry_nutrition_to_gsheets(
        nutritionist, pantry_list, gsheets_helper
    ):
        # TODO expand tests to cover different options
        nutritionist.sync_pantry_nutrition_to_gsheets(
            pantry_list, gsheets_helper, override_value=True
        )


# TODO add regular test when re-syncing to check that values have not changed
