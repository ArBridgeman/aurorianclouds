import pandas as pd
from sous_chef.grocery_list.generate_grocery_list._aggregated import (
    GroceryListAggregated,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


class GroceryListExtractedFromMenu(GroceryListAggregated):
    def get_grocery_list_from_menu(self, menu: pd.DataFrame) -> pd.DataFrame:
        for _, row in menu.iterrows():
            for_day = row.prep_datetime.date()
            if row["type"] == "ingredient":
                self.add_manual_ingredient(row, for_day=for_day)
            elif row["type"] == "recipe":
                response = self.add_recipe_ingredients(row, for_day=for_day)
                print(response)
        self._aggregate_grocery_list()
        return self.grocery_list
