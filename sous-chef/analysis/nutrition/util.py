from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.nutrition.provide_nutritional_info import Nutritionist


def get_nutritionist():
    with initialize(version_base=None, config_path="../../config/"):
        config = compose(config_name="nutrition").nutrition
        return Nutritionist(config=config)


def get_gsheets_helper():
    with initialize(version_base=None, config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


def get_nutrition_data():
    nutritionist = get_nutritionist()
    gsheets_helper = get_gsheets_helper()
    return nutritionist.get_pantry_nutrition_from_gsheets(
        gsheets_helper=gsheets_helper
    )
