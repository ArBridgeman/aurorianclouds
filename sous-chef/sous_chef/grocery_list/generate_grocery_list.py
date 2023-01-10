from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import chain
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pint import Unit
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
from sous_chef.formatter.format_str import convert_number_to_str
from sous_chef.formatter.format_unit import UnitFormatter, unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from sous_chef.menu.create_menu import MenuIngredient, MenuRecipe
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import Recipe
from structlog import get_logger
from termcolor import cprint

# TODO method to mark ingredients that can only be bought the day before

FILE_LOGGER = get_logger(__name__)


@dataclass
class GroceryListIncompleteError(Exception):
    custom_message: str
    message: str = "[grocery list had errors]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} {self.custom_message}"


@dataclass
class GroceryList:
    config: DictConfig
    due_date_formatter: DueDatetimeFormatter
    unit_formatter: UnitFormatter
    ingredient_field: IngredientField
    # TODO do properly? pass everything inside methods? only set final list?
    queue_menu_recipe: List[MenuRecipe] = None
    queue_preparation: pd.DataFrame = None
    grocery_list_raw: pd.DataFrame = None
    grocery_list: pd.DataFrame = None
    second_shopping_date: date = field(init=False)
    second_shopping_day_group: List = field(init=False)
    has_errors: bool = False
    app_week_label: str = field(init=False)

    def __post_init__(self):
        self.second_shopping_date = (
            self.due_date_formatter.get_date_relative_to_anchor(
                self.config.shopping.secondary_day
            ).date()
        )
        self.second_shopping_day_group = self.config.shopping.secondary_group

        calendar_week = self.due_date_formatter.get_calendar_week()
        self.app_week_label = f"app-week-{calendar_week}"

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

    def upload_grocery_list_to_todoist(self, todoist_helper: TodoistHelper):
        if self.has_errors:
            raise GroceryListIncompleteError(
                "will not send to ToDoist until fixed"
            )

        # TODO what should be in todoist (e.g. dry mode & messages?)
        project_name = self.config.todoist.project_name
        if self.config.todoist.remove_existing_task:
            todoist_helper.delete_all_items_in_project(
                project_name, only_with_label=self.app_week_label
            )

        for section, group in self.grocery_list.groupby("aisle_group"):
            if section in self.config.todoist.skip_group:
                FILE_LOGGER.warning(
                    "[skip group]",
                    action="do not add to todoist",
                    aisle_group=section,
                    ingredient_list=group["item"].values,
                )
                continue

            project_id = todoist_helper.get_project_id(project_name)
            section_id = todoist_helper.get_section_id(
                project_id=project_id, section_name=section
            )

            # TODO CODE-197 add barcode (and later item name in description)
            for _, entry in group.iterrows():
                todoist_helper.add_task_to_project(
                    task=self._format_ingredient_str(entry),
                    due_date=self.second_shopping_date
                    if entry["get_on_second_shopping_day"]
                    else None,
                    label_list=entry["from_recipe"]
                    + entry["for_day_str"]
                    + [self.app_week_label],
                    description=str(entry["barcode"]),
                    project=project_name,
                    project_id=project_id,
                    section=section,
                    section_id=section_id,
                    priority=2 if entry["get_on_second_shopping_day"] else 1,
                )

    def send_preparation_to_todoist(self, todoist_helper: TodoistHelper):
        # TODO separate service? need freezer check for defrosts
        project_name = self.config.preparation.project_name
        if self.config.todoist.remove_existing_prep_task:
            todoist_helper.delete_all_items_in_project(
                project_name, only_with_label=self.app_week_label
            )

        if self.queue_preparation is not None:
            for _, row in self.queue_preparation.iterrows():
                todoist_helper.add_task_to_project(
                    task=row.task,
                    project=project_name,
                    label_list=list(
                        chain.from_iterable([row.from_recipe, row.for_day_str])
                    )
                    + ["prep", self.app_week_label],
                    due_date=row.due_date,
                    priority=self.config.preparation.task_priority,
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
        item_plural: str,
        store: str,
        barcode: str,
        from_recipe: str,
        for_day: datetime,
    ):
        if self.grocery_list_raw is None:
            self.grocery_list_raw = pd.DataFrame()

        new_entry = pd.DataFrame(
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
                "item_plural": item_plural,
                "store": store,
                "barcode": barcode,
                "from_recipe": from_recipe,
                "for_day": for_day,
                "for_day_str": for_day.strftime("%a"),
                "get_on_second_shopping_day": self._get_on_second_shopping_day(
                    for_day=for_day, food_group=food_group
                ),
            },
            index=[0],
        )

        self.grocery_list_raw = pd.concat(
            [self.grocery_list_raw, new_entry], ignore_index=True
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
                item_plural=x.item_plural,
                store=x.store,
                barcode=x.barcode,
                from_recipe=manual_ingredient.from_recipe,
                for_day=manual_ingredient.for_day,
            )
            for manual_ingredient in manual_ingredient_list
            if (x := access_ingredient(manual_ingredient))
        ]

    def _add_menu_recipe_to_queue(self, menu_recipe_list: list[MenuRecipe]):
        if self.queue_menu_recipe is None:
            self.queue_menu_recipe = []
        self.queue_menu_recipe.extend(menu_recipe_list)

    def _add_preparation_task_to_queue(
        self,
        task: str,
        due_date: datetime,
        from_recipe: List[str],
        for_day_str: List[str],
    ):
        preparation_task = pd.DataFrame(
            {
                "task": [task],
                "due_date": [due_date],
                "from_recipe": [from_recipe],
                "for_day_str": [for_day_str],
            }
        )
        if self.queue_preparation is None:
            self.queue_preparation = preparation_task
        else:
            self.queue_preparation = pd.concat(
                [self.queue_preparation, preparation_task]
            )

    def _add_referenced_recipe_to_queue(
        self, menu_recipe: MenuRecipe, recipe_list: List[Recipe]
    ):
        def _check_yes_no(text: str) -> str:
            response = None
            while response not in ["Y", "N"]:
                response = input(f"\n{text} [Y/N] ").upper()
            return response

        def _get_schedule_day_hour_minute() -> datetime:
            day = None
            while day not in Weekday.name_list("capitalize"):
                day = input("\nWeekday: ").capitalize()

            meal_time = None
            meal_times = MealTime.name_list("lower")
            while meal_time not in meal_times:
                meal_time = input(f"\nMealtime {meal_times}: ").lower()
            meal_time = MealTime[meal_time].value
            return self.due_date_formatter.get_due_datetime_with_time(
                weekday=day, hour=meal_time["hour"], minute=meal_time["minute"]
            )

        def _give_referenced_recipe_details():
            total_factor = menu_recipe.eat_factor + menu_recipe.freeze_factor
            print("\n#### REFERENCED RECIPE CHECK ####")
            print(f"- from recipe: {menu_recipe.recipe.title}")
            print(f"-- total_factor: {total_factor}")
            print(f"-- for day: {menu_recipe.for_day.strftime('%a')}")
            print(f"- referenced recipe: {recipe.title}")
            print(f"-- amount needed: {recipe.amount}")
            print(f"-- total time: {recipe.time_total}")

        for recipe in recipe_list:
            from_recipe = f"{recipe.title}_{menu_recipe.recipe.title}"
            menu_sub_recipe = MenuRecipe(
                from_recipe=from_recipe,
                for_day=menu_recipe.for_day,
                eat_factor=menu_recipe.eat_factor * recipe.factor,
                freeze_factor=menu_recipe.freeze_factor * recipe.factor,
                recipe=recipe,
            )

            # TODO make more robust to other methods
            if self.config.run_mode.with_todoist:
                _give_referenced_recipe_details()
                if _check_yes_no(f"Need to make '{recipe.title}'?") == "Y":
                    self._add_menu_recipe_to_queue([menu_sub_recipe])

                    if (
                        recipe.time_total is None
                        or recipe.time_total > timedelta(minutes=15)
                    ):
                        if (
                            _check_yes_no(
                                f"Separately schedule '{recipe.title}'?"
                            )
                            == "Y"
                        ):
                            self._add_preparation_task_to_queue(
                                f"[PREP] {recipe.amount}",
                                due_date=_get_schedule_day_hour_minute(),
                                from_recipe=[from_recipe],
                                for_day_str=[
                                    menu_sub_recipe.for_day.strftime("%a")
                                ],
                            )

    def _aggregate_grocery_list(self):
        # do not drop nas, as some items are dimensionless (None)
        if self.grocery_list is None:
            self.grocery_list = pd.DataFrame()

        # TODO add for_day option

        # TODO fix pantry list to not do lidl for meats (real group instead)
        grouped = self.grocery_list_raw.groupby(
            ["item", "dimension", "get_on_second_shopping_day"], dropna=False
        )
        for name, group in grouped:
            # if more than 1 unit, use largest
            if group.pint_unit.nunique() > 1:
                group = self._get_group_in_same_pint_unit(group)
            agg_group = self._aggregate_group_to_grocery_list(group)
            self.grocery_list = pd.concat(
                [self.grocery_list, agg_group], ignore_index=True
            )

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
        agg = (
            group.groupby(groupby_columns, as_index=False, dropna=False)
            .agg(
                quantity=("quantity", "sum"),
                is_staple=("is_staple", "first"),
                food_group=("food_group", "first"),
                item_plural=("item_plural", "first"),
                store=("store", "first"),
                barcode=("barcode", "first"),
                from_recipe=("from_recipe", lambda x: sorted(list(set(x)))),
                for_day=("for_day", "min"),
                for_day_str=("for_day_str", lambda x: sorted(list(set(x)))),
                get_on_second_shopping_day=(
                    "get_on_second_shopping_day",
                    "first",
                ),
            )
            .astype({"is_staple": bool, "barcode": str})
        )
        if self.config.ingredient_replacement.can_to_dried_bean.is_active:
            agg = agg.apply(self._override_can_to_dried_bean, axis=1)
        return agg

    def _format_bean_prep_task_str(
        self, row: pd.Series, freeze_quantity: int
    ) -> str:
        ingredient_str = self._format_ingredient_str(row)
        unit_str = self.unit_formatter.get_unit_str(
            freeze_quantity, unit_registry.can
        )
        return (
            f"[BEAN PREP] {ingredient_str} "
            f"(freeze: {freeze_quantity} {unit_str})"
        )

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

    def _get_on_second_shopping_day(
        self, for_day: datetime, food_group: str
    ) -> bool:
        return (for_day.date() >= self.second_shopping_date) and (
            food_group.casefold() in self.second_shopping_day_group
        )

    def _override_can_to_dried_bean(self, row: pd.Series) -> pd.Series:
        config_bean_prep = self.config.bean_prep
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

        self._add_preparation_task_to_queue(
            task=self._format_bean_prep_task_str(
                row, config_bean.number_can_to_freeze
            ),
            due_date=self.due_date_formatter.replace_time_with_meal_time(
                due_date=row.for_day
                - timedelta(days=config_bean_prep.prep_day_before),
                meal_time=config_bean_prep.prep_meal,
            ),
            from_recipe=row.from_recipe,
            for_day_str=row.for_day.strftime("%a"),
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
            error_list,
        ) = self.ingredient_field.parse_ingredient_field(
            ingredient_field=menu_recipe.recipe.ingredients
        )
        self._add_referenced_recipe_to_queue(menu_recipe, recipe_list)
        self._process_ingredient_list(menu_recipe, ingredient_list)
        # TO DO somehow get back to a google drive doc
        if error_list:
            self.has_errors = True
            cprint("\t" + "\n\t".join(error_list), "green")

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
                item_plural=ingredient.item_plural,
                store=ingredient.store,
                barcode=ingredient.barcode,
                from_recipe=menu_recipe.from_recipe,
                for_day=menu_recipe.for_day,
            )

    def _transform_food_to_aisle_group(self, food_group: str):
        aisle_map = self.config.food_group_to_aisle_map
        # food_group may be none, particularly if pantry item not found
        if food_group and food_group.casefold() in aisle_map:
            return aisle_map[food_group.casefold()]
        return "Unknown"
