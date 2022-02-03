from dataclasses import dataclass
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pint import Unit, UnitRegistry
from sous_chef.formatter.format_str import convert_float_to_str
from sous_chef.formatter.format_unit import (
    convert_quantity_to_desired_unit,
    get_unit_as_abbreviated_str,
)
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
)
from sous_chef.menu.create_menu import Menu, MenuIngredient, MenuRecipe
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import Recipe
from structlog import get_logger

# TODO method to scale recipe to desired servings
# TODO method to mark ingredients that can only be bought the day before

FILE_LOGGER = get_logger(__name__)


@dataclass
class GroceryList:
    config: DictConfig
    ingredient_field_formatter: IngredientFieldFormatter
    menu: Menu
    # TODO do properly? pass everything inside methods? only set final list?
    queue_menu_recipe = []
    queue_bean_preparation = []
    grocery_list_raw: pd.DataFrame = pd.DataFrame()
    grocery_list = pd.DataFrame()

    def get_grocery_list(self):
        self._parse_menu_entries()
        self._process_recipe_queue()
        self._aggregate_grocery_list_by_item_and_dimension()
        self._save_aggregated_grocery_list()

    def upload_grocery_list_to_todoist(self, todoist_helper: TodoistHelper):
        # TODO what should be in todoist (e.g. dry mode & messages?)
        project_name = self.config.todoist.project_name

        if self.config.todoist.remove_existing_task:
            # TODO move repeat delete, etc. into todoist option
            # TODO add timeout option?
            [
                todoist_helper.delete_all_items_in_project(project_name)
                for _ in range(3)
            ]

        for _, ingredient in self.grocery_list.iterrows():
            if ingredient.aisle_group in self.config.todoist.skip_group:
                FILE_LOGGER.warning(
                    "[skip group]",
                    action="do not add to todoist",
                    aisle_group=ingredient.aisle_group,
                    ingredient=ingredient["item"],
                )
                continue

            formatted_ingredient = self._format_ingredient_as_str(ingredient)
            todoist_helper.add_item_to_project(
                item=formatted_ingredient,
                project=project_name,
                section=ingredient.aisle_group,
                labels=ingredient.from_recipe + ingredient.from_day,
            )

    def send_bean_preparation_to_todoist(self, todoist_helper: TodoistHelper):
        # TODO separate service? need freezer check for defrosts
        # TODO generalize beyond beans
        from sous_chef.date.get_date import get_due_date

        project_name = "Menu"
        if self.config.todoist.remove_existing_task:
            [
                todoist_helper.delete_all_items_in_project(project_name)
                for _ in range(3)
            ]

        # add entry on Saturday
        due_date = get_due_date(
            "saturday",
            hour=9,
            minute=0,
        )
        due_date_dict = {"string": due_date.strftime("on %Y-%m-%d at %H:%M")}

        for item in self.queue_bean_preparation:
            ingredient_str = self._format_ingredient_as_str(item["group"])
            freeze_str = f"{item['number_can_to_freeze']} can"
            task_str = f"BEAN PREP: {ingredient_str} (freeze: {freeze_str})"
            todoist_helper.add_item_to_project(
                task_str,
                project_name,
                labels=item["group"].from_recipe + item["group"].from_day,
                due_date_dict=due_date_dict,
            )

    def _add_to_grocery_list_raw(
        self,
        quantity: float,
        unit: str,
        pint_unit: Unit,
        item: str,
        is_staple: bool,
        is_optional: bool,
        food_group: str,
        store: str,
        item_plural: str,
        from_recipe: str,
        from_day: str,
    ):

        self.grocery_list_raw = self.grocery_list_raw.append(
            {
                "quantity": quantity,
                "unit": unit,
                "pint_unit": pint_unit,
                "dimension": str(pint_unit.dimensionality)
                if pint_unit
                else None,
                "item": item,
                "is_staple": is_staple,
                "is_optional": is_optional,
                "food_group": food_group,
                "store": store,
                "item_plural": item_plural,
                "from_recipe": from_recipe,
                "from_day": from_day,
            },
            ignore_index=True,
        )

    def _add_bulk_manual_ingredient_to_grocery_list(
        self, manual_ingredient_list: List[MenuIngredient]
    ):
        [
            self._add_to_grocery_list_raw(
                quantity=manual_ingredient.ingredient.quantity,
                unit=manual_ingredient.ingredient.unit,
                pint_unit=manual_ingredient.ingredient.pint_unit,
                item=manual_ingredient.ingredient.item,
                is_staple=manual_ingredient.ingredient.is_staple,
                is_optional=manual_ingredient.ingredient.is_optional,
                food_group=manual_ingredient.ingredient.group,
                store=manual_ingredient.ingredient.store,
                item_plural=manual_ingredient.ingredient.item_plural,
                from_recipe=manual_ingredient.from_recipe,
                from_day=manual_ingredient.from_day,
            )
            for manual_ingredient in manual_ingredient_list
        ]

    def _add_referenced_recipe_to_queue(
        self, menu_recipe: MenuRecipe, recipe_list: List[Recipe]
    ):
        for recipe in recipe_list:
            # referenced recipe modified by factor
            recipe.factor *= menu_recipe.factor
            new_menu_recipe = MenuRecipe(
                from_recipe=f"{recipe.title}_{menu_recipe.recipe.title}",
                from_day=menu_recipe.from_day,
                factor=recipe.factor,
                recipe=recipe,
            )
            self.queue_menu_recipe.append(new_menu_recipe)

    def _aggregate_group_to_grocery_list(
        self, group: pd.DataFrame
    ) -> pd.DataFrame:
        groupby_columns = ["unit", "item", "is_optional"]
        # set dropna to false, as item may not have unit
        agg = group.groupby(groupby_columns, as_index=False, dropna=False).agg(
            quantity=("quantity", "sum"),
            is_staple=("is_staple", "first"),
            food_group=("food_group", "first"),
            store=("store", "first"),
            item_plural=("item_plural", "first"),
            from_recipe=("from_recipe", lambda x: list(set(x))),
            from_day=("from_day", lambda x: list(set(x))),
        )

        if self.config.ingredient_replacement.can_to_dried_bean.is_active:
            agg = agg.apply(self._override_can_to_dried_bean, axis=1)

        # set item to plural
        mask_plural = (agg["quantity"] > 1) & (agg["unit"].isna())
        agg.loc[mask_plural, "item"] = agg.loc[mask_plural, "item_plural"]

        return agg.drop(columns=["item_plural"])

    def _aggregate_grocery_list_by_item_and_dimension(self):
        # do not drop nas, as some items are dimensionless (None)
        grocery_list = pd.DataFrame()
        grouped = self.grocery_list_raw.groupby(
            ["item", "dimension"], dropna=False
        )
        for name, group in grouped:
            # if more than 1 unit, use largest
            if group.pint_unit.nunique() > 1:
                self._get_group_in_same_pint_unit(group)
            group["unit"] = group.apply(
                self._get_pint_unit_as_abbreviated_unit, axis=1
            )
            agg_group = self._aggregate_group_to_grocery_list(group)
            grocery_list = grocery_list.append(agg_group)

        # get aisle/store
        grocery_list["aisle_group"] = grocery_list.food_group.apply(
            self._transform_food_to_aisle_group
        )

        # replace aisle group to store name when not default store
        grocery_list["aisle_group"] = grocery_list.apply(
            self._override_aisle_group_when_not_default_store, axis=1
        )

        # reset index and set in class
        self.grocery_list = grocery_list.reset_index(drop=True)

    @staticmethod
    def _format_ingredient_as_str(ingredient: pd.Series) -> str:
        quantity_str = convert_float_to_str(ingredient.quantity)

        ingredient_str = "{item}, {quantity}".format(
            item=ingredient["item"], quantity=quantity_str
        )

        if not pd.isnull(ingredient.unit):
            ingredient_str += f" {ingredient.unit}"

        if ingredient.is_optional:
            ingredient_str += " (optional)"

        return ingredient_str

    @staticmethod
    def _get_group_in_same_pint_unit(group):
        largest_unit = max(group.pint_unit.unique())
        group["quantity"], group["pint_unit"] = zip(
            *group.apply(
                lambda row: convert_quantity_to_desired_unit(
                    row.quantity, row.pint_unit, largest_unit
                ),
                axis=1,
            )
        )

    @staticmethod
    def _get_pint_unit_as_abbreviated_unit(row: pd.Series):
        if row.pint_unit is not None:
            return get_unit_as_abbreviated_str(row.pint_unit)
        return row.unit

    def _override_can_to_dried_bean(self, row: pd.Series) -> pd.DataFrame:
        bean_config = self.config.ingredient_replacement.can_to_dried_bean
        # TODO move to ingredient formatter or somewhere more appropriate?
        # TODO should we do this with other things like rice?
        # TODO create custom pint unit or table between wet & dry?
        if row["item"] in bean_config.bean_list:
            row["item"] = f"dried {row['item']}"
            row["food_group"] = "Beans"
            # TODO handle other cases?
            if row["unit"] in ["can", "cans"]:
                row["unit"] = "g"
                row["pint_unit"] = UnitRegistry().gram
                row["quantity"] = (
                    row["quantity"] + bean_config.number_can_to_freeze
                ) * bean_config.g_per_can
                row["item_plural"] = "s"
            self.queue_bean_preparation.append(
                {
                    "group": row,
                    "number_can_to_freeze": bean_config.number_can_to_freeze,
                }
            )
        return row

    def _override_aisle_group_when_not_default_store(self, row):
        # if pantry item not found, store not set
        if row.store:
            if row.store.casefold() != self.config.default_store.casefold():
                return row.store
        return row.aisle_group

    def _process_recipe_queue(self):
        while len(self.queue_menu_recipe) > 0:
            current_recipe = self.queue_menu_recipe[0]
            FILE_LOGGER.info(
                "[grocery list]", recipe=current_recipe.recipe.title
            )
            self._parse_ingredient_from_recipe(current_recipe)
            self.queue_menu_recipe = self.queue_menu_recipe[1:]

    def _parse_ingredient_from_recipe(self, menu_recipe: MenuRecipe):
        (
            recipe_list,
            ingredient_list,
        ) = self.ingredient_field_formatter.parse_ingredient_field(
            menu_recipe.recipe.ingredient_field
        )
        self._add_referenced_recipe_to_queue(menu_recipe, recipe_list)
        self._process_ingredient_list(menu_recipe, ingredient_list)

    def _process_ingredient_list(
        self, menu_recipe: MenuRecipe, ingredient_list: List[Ingredient]
    ):
        for ingredient in ingredient_list:
            self._add_to_grocery_list_raw(
                quantity=ingredient.quantity * menu_recipe.factor,
                unit=ingredient.unit,
                pint_unit=ingredient.pint_unit,
                item=ingredient.item,
                is_staple=ingredient.is_staple,
                is_optional=ingredient.is_optional,
                food_group=ingredient.group,
                store=ingredient.store,
                item_plural=ingredient.item_plural,
                from_recipe=menu_recipe.from_recipe,
                from_day=menu_recipe.from_day,
            )

    def _parse_menu_entries(self):
        ingredient_list, recipe_list = self.menu.get_menu_for_grocery_list()
        self._add_bulk_manual_ingredient_to_grocery_list(ingredient_list)
        self.queue_menu_recipe.extend(recipe_list)

    def _save_aggregated_grocery_list(self):
        self.grocery_list.to_csv("grocery_list.csv")

    def _transform_food_to_aisle_group(self, food_group: str):
        aisle_map = self.config.food_group_to_aisle_map
        # food_group may be none, particularly if pantry item not found
        if food_group and food_group.casefold() in aisle_map:
            return aisle_map[food_group.casefold()]
        else:
            return "Unknown"
