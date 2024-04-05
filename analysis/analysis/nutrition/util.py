import pandas as pd
from hydra import compose, initialize
from sous_chef.nutrition.provide_nutritional_info import Nutritionist

from utilities.api.gsheets_api import GsheetsHelper


def get_nutritionist():
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="nutrition").nutrition
        return Nutritionist(config=config)


def get_gsheets_helper():
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/api"
    ):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


def get_nutrition_data():
    nutritionist = get_nutritionist()
    gsheets_helper = get_gsheets_helper()
    nutri_df = nutritionist.get_pantry_nutrition_from_gsheets(
        gsheets_helper=gsheets_helper
    )
    nutri_manual_df = gsheets_helper.get_worksheet(
        workbook_name="nutrition", worksheet_name="nutrition-manual"
    )
    nutri_df = pd.concat(
        [nutri_df, nutri_manual_df], ignore_index=True, copy=False
    )
    # TODO better to have handled in nutritionist
    return nutri_df.astype(
        {
            "per_100g_carbohydrates": "float64",
            "per_100g_sugars": "float64",
            "per_100g_energy_kcal": "float64",
            "per_100g_fat": "float64",
            "per_100g_saturated_fat": "float64",
            "per_100g_fiber": "float64",
            "per_100g_proteins": "float64",
        }
    ).fillna(0)
