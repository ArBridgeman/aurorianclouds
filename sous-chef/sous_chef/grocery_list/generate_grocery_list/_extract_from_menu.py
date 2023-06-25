from typing import List

import pandas as pd
from sous_chef.grocery_list.generate_grocery_list._aggregated import (
    GroceryListAggregated,
)
from sous_chef.menu.create_menu._for_grocery_list import (
    MenuIngredient,
    MenuRecipe,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


class GroceryListExtractedFromMenu(GroceryListAggregated):
    def get_grocery_list_from_menu(
        self,
        menu_ingredient_list: List[MenuIngredient],
        menu_recipe_list: List[MenuRecipe],
    ) -> pd.DataFrame:
        self._add_bulk_manual_ingredient_to_grocery_list(menu_ingredient_list)
        self._add_menu_recipe_to_queue(menu_recipe_list)
        self._process_recipe_queue()
        self._aggregate_grocery_list()
        return self.grocery_list

    def _add_bulk_manual_ingredient_to_grocery_list(
        self, manual_ingredient_list: List[MenuIngredient]
    ):
        def access_ingredient(x: MenuIngredient):
            return x.ingredient

        [
            self._add_to_grocery_list_raw(
                quantity=x.quantity,
                unit=x.unit,
                pint_unit=x.pint_unit,
                item=x.item,
                is_staple=x.is_staple,
                is_optional=x.is_optional,
                food_group=x.group,
                item_plural=x.item_plural,
                store=x.store,
                barcode=x.barcode,
                from_recipe=manual_ingredient.from_recipe,
                for_day=manual_ingredient.for_day,
            )
            for manual_ingredient in manual_ingredient_list
            if (x := access_ingredient(manual_ingredient))
        ]

    def _process_recipe_queue(self):
        while len(self.queue_menu_recipe) > 0:
            current_recipe = self.queue_menu_recipe[0]
            FILE_LOGGER.info(
                "[grocery list]",
                action="processing",
                recipe=current_recipe.recipe.title,
            )
            self._parse_ingredient_from_recipe(current_recipe)
            self.queue_menu_recipe = self.queue_menu_recipe[1:]
