from dataclasses import dataclass
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pint import Unit
from sous_chef.formatter.format_str import convert_number_to_str
from sous_chef.formatter.format_unit import UnitFormatter, unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
)
from sous_chef.menu.create_menu import MenuIngredient, MenuRecipe
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import Recipe
from structlog import get_logger

# TODO method to mark ingredients that can only be bought the day before

FILE_LOGGER = get_logger(__name__)


@dataclass
class GroceryList:
    config: DictConfig
    unit_formatter: UnitFormatter
    ingredient_field_formatter: IngredientFieldFormatter
    # TODO do properly? pass everything inside methods? only set final list?
    queue_menu_recipe: List[MenuRecipe] = None
    queue_bean_preparation: List = None
    grocery_list_raw: pd.DataFrame = None
    grocery_list: pd.DataFrame = None

    def get_grocery_list_from_menu(
        self,
        menu_ingredient_list: List[MenuIngredient],
        menu_recipe_list: List[MenuRecipe],
    ):
        self._add_bulk_manual_ingredient_to_grocery_list(menu_ingredient_list)
        self._add_menu_recipe_to_queue(menu_recipe_list)
        self._process_recipe_queue()
        self._aggregate_grocery_list_by_item_and_dimension()

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

        for name, group in self.grocery_list.groupby("aisle_group"):
            if name in self.config.todoist.skip_group:
                FILE_LOGGER.warning(
                    "[skip group]",
                    action="do not add to todoist",
                    aisle_group=name,
                    ingredient_list=group["item"].values,
                )
                continue

            todoist_helper.add_task_list_to_project_with_label_list(
                task_list=group.apply(
                    self._format_ingredient_str, axis=1
                ).tolist(),
                project=project_name,
                section=name,
                label_list=group[["from_recipe", "from_day"]].values.tolist(),
            )

    def send_bean_preparation_to_todoist(self, todoist_helper: TodoistHelper):
        # TODO separate service? need freezer check for defrosts
        # TODO generalize beyond beans
        from sous_chef.date.get_due_date import DueDatetimeFormatter

        bean_prep = self.config.bean_prep
        project_name = bean_prep.project_name
        if self.config.todoist.remove_existing_task:
            [
                todoist_helper.delete_all_items_in_project(project_name)
                for _ in range(3)
            ]

        due_date = DueDatetimeFormatter(
            bean_prep.anchor_day
        ).get_due_datetime_with_hour_minute(
            weekday=bean_prep.prep_day, hour=bean_prep.prep_hour, minute=0
        )

        # TODO change queue_bean_preparation into dataframe to use pandas here
        if self.queue_bean_preparation:
            for item in self.queue_bean_preparation:
                label_list = item["group"].from_recipe + item["group"].from_day
                todoist_helper.add_task_to_project(
                    task=self._format_bean_prep_task_str(item),
                    project=project_name,
                    label_list=label_list,
                    due_date=due_date,
                    priority=4,
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
        if self.grocery_list_raw is None:
            self.grocery_list_raw = pd.DataFrame()

        self.grocery_list_raw = self.grocery_list_raw.append(
            {
                "quantity": quantity,
                # TODO do we need unit?
                "unit": unit,
                "pint_unit": pint_unit,
                # TODO already add to Ingredient when first created?
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
                store=x.store,
                item_plural=x.item_plural,
                from_recipe=manual_ingredient.from_recipe,
                from_day=manual_ingredient.from_day,
            )
            for manual_ingredient in manual_ingredient_list
            if (x := access_ingredient(manual_ingredient))
        ]

    def _add_menu_recipe_to_queue(self, menu_recipe_list: list[MenuRecipe]):
        if self.queue_menu_recipe is None:
            self.queue_menu_recipe = []
        self.queue_menu_recipe.extend(menu_recipe_list)

    def _add_referenced_recipe_to_queue(
        self, menu_recipe: MenuRecipe, recipe_list: List[Recipe]
    ):
        for recipe in recipe_list:
            menu_recipe = MenuRecipe(
                from_recipe=f"{recipe.title}_{menu_recipe.recipe.title}",
                from_day=menu_recipe.from_day,
                eat_factor=menu_recipe.eat_factor * recipe.factor,
                freeze_factor=menu_recipe.freeze_factor * recipe.factor,
                recipe=recipe,
            )
            self._add_menu_recipe_to_queue([menu_recipe])

    def _aggregate_grocery_list_by_item_and_dimension(self):
        # do not drop nas, as some items are dimensionless (None)
        if self.grocery_list is None:
            self.grocery_list = pd.DataFrame()

        grouped = self.grocery_list_raw.groupby(
            ["item", "dimension"], dropna=False
        )
        for name, group in grouped:
            # if more than 1 unit, use largest
            if group.pint_unit.nunique() > 1:
                group = self._get_group_in_same_pint_unit(group)
            agg_group = self._aggregate_group_to_grocery_list(group)
            self.grocery_list = self.grocery_list.append(agg_group)

        # get aisle/store
        self.grocery_list["aisle_group"] = self.grocery_list.food_group.apply(
            self._transform_food_to_aisle_group
        )

        # replace aisle group to store name when not default store
        self.grocery_list["aisle_group"] = self.grocery_list.apply(
            self._override_aisle_group_when_not_default_store, axis=1
        )

        # reset index and set in class
        self.grocery_list = self.grocery_list.reset_index(drop=True)

    def _aggregate_group_to_grocery_list(
        self, group: pd.DataFrame
    ) -> pd.DataFrame:
        groupby_columns = ["unit", "pint_unit", "item", "is_optional"]
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
        return agg

    def _format_bean_prep_task_str(self, item: dict) -> str:
        ingredient_str = self._format_ingredient_str(item["group"])

        freeze_quantity = item["number_can_to_freeze"]
        unit_str = self.unit_formatter.get_unit_str(
            freeze_quantity, unit_registry.can
        )
        freeze_str = f"{freeze_quantity} {unit_str}"

        return f"BEAN PREP: {ingredient_str} (freeze: {freeze_str})"

    def _format_ingredient_str(self, ingredient: pd.Series) -> str:
        item = ingredient["item"]
        if ingredient["quantity"] > 1 and pd.isnull(ingredient["pint_unit"]):
            item = ingredient["item_plural"]
        ingredient_str = "{item}, {quantity}".format(
            item=item, quantity=convert_number_to_str(ingredient.quantity)
        )

        # TODO: do we need .unit anymore?
        if not pd.isnull(ingredient.pint_unit):
            unit_str = self.unit_formatter.get_unit_str(
                ingredient["quantity"], ingredient["pint_unit"]
            )
            ingredient_str += f" {unit_str}"

        if ingredient.is_optional:
            ingredient_str += " (optional)"

        return ingredient_str

    def _get_group_in_same_pint_unit(self, group: pd.DataFrame) -> pd.DataFrame:
        largest_unit = max(group.pint_unit.unique())
        group["quantity"], group["unit"], group["pint_unit"] = zip(
            *group.apply(
                lambda row: self.unit_formatter.convert_to_desired_unit(
                    row.quantity, row.pint_unit, largest_unit
                ),
                axis=1,
            )
        )
        return group

    def _override_can_to_dried_bean(self, row: pd.Series) -> pd.Series:
        config_bean = self.config.ingredient_replacement.can_to_dried_bean
        # TODO better in ingredient formatter with prep-tag? similar cases?
        if row["item"] not in config_bean.bean_list:
            return row
        if row["pint_unit"] != unit_registry.can:
            return row

        cans = row["quantity"] + config_bean.number_can_to_freeze
        row["item"] = f"dried {row['item']}"
        row["item_plural"] = f"dried {row['item_plural']}"
        row["food_group"] = "Beans"
        row["unit"] = "g"
        row["pint_unit"] = unit_registry.gram
        row["quantity"] = cans * config_bean.g_per_can

        if self.queue_bean_preparation is None:
            self.queue_bean_preparation = []
        self.queue_bean_preparation.append(
            {
                "group": row,
                "number_can_to_freeze": config_bean.number_can_to_freeze,
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
                "[grocery list]",
                action="processing",
                recipe=current_recipe.recipe.title,
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
        # TODO if future pandas, then wouldn't need this function at all
        for ingredient in ingredient_list:
            self._add_to_grocery_list_raw(
                quantity=ingredient.quantity
                * (menu_recipe.eat_factor + menu_recipe.freeze_factor),
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

    def _transform_food_to_aisle_group(self, food_group: str):
        aisle_map = self.config.food_group_to_aisle_map
        # food_group may be none, particularly if pantry item not found
        if food_group and food_group.casefold() in aisle_map:
            return aisle_map[food_group.casefold()]
        return "Unknown"
