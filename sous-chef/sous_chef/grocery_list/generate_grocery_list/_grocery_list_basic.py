from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Tuple

import pandas as pd
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
from sous_chef.formatter.format_str import convert_number_to_str
from sous_chef.formatter.format_unit import UnitFormatter, unit_registry
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import Recipe
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
class GroceryListBasic:
    config: DictConfig
    due_date_formatter: DueDatetimeFormatter
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    unit_formatter: UnitFormatter
    ingredient_field: IngredientField
    # TODO do properly? pass everything inside methods? only set final list?
    queue_preparation: pd.DataFrame = None
    grocery_list_raw: pd.DataFrame = None
    grocery_list: pd.DataFrame = None
    primary_shopping_date: date = None
    secondary_shopping_date: date = None
    second_shopping_day_group: Tuple = ()
    has_errors: bool = False
    app_week_label: str = field(init=False)

    def __post_init__(self):
        self.primary_shopping_date = (
            self.due_date_formatter.get_date_relative_to_anchor(
                self.config.shopping.primary_day
            )
        ).date()
        if (
            self.primary_shopping_date
            >= self.due_date_formatter.get_anchor_date()
        ):
            self.primary_shopping_date -= timedelta(days=7)

        if self.config.shopping.secondary_day:
            self.secondary_shopping_date = (
                self.due_date_formatter.get_date_relative_to_anchor(
                    self.config.shopping.secondary_day
                ).date()
            )
            self.second_shopping_day_group = (
                self.config.shopping.secondary_group
            )

        calendar_week = self.due_date_formatter.get_calendar_week()
        self.app_week_label = f"app-week-{calendar_week}"

    def add_manual_ingredient(
        self, manual_ingredient: pd.Series, for_day: date
    ):
        ingredient = self.ingredient_formatter.format_manual_ingredient(
            quantity=float(manual_ingredient["eat_factor"]),
            unit=manual_ingredient["eat_unit"],
            item=manual_ingredient["item"],
        )

        self._add_to_grocery_list_raw(
            quantity=ingredient.quantity,
            ingredient=ingredient,
            from_recipe="manual",
            for_day=for_day,
        )

    def add_recipe_ingredients(self, menu_recipe: pd.Series, for_day: date):
        FILE_LOGGER.info(
            "[grocery list]", action="processing", recipe=menu_recipe["item"]
        )

        # TODO catch if recipe not found and add to errors
        recipe = self.recipe_book.get_recipe_by_title(menu_recipe["item"])

        first_recipe = menu_recipe.copy()
        first_recipe["recipe"] = recipe
        first_recipe["from_recipe"] = recipe.title
        first_recipe["for_day"] = for_day

        recipe_queue = [first_recipe]
        response = {
            "recipe": recipe.title,
            "has_error": False,
            "ref_recipes": [],
            "errors": {},
        }

        # TODO prevent infinite loop
        while len(recipe_queue) > 0:
            current_recipe = recipe_queue.pop(0)
            (
                ref_recipe_list,
                ingredient_list,
                error_list,
            ) = self.ingredient_field.parse_ingredient_field(
                ingredient_field=current_recipe.recipe.ingredients
            )

            if current_recipe.recipe.title != first_recipe.recipe.title:
                response["ref_recipes"].append(current_recipe.recipe.title)

            # TODO need to change if API; can't respond via CLI
            self._add_referenced_recipe_to_queue(
                menu_recipe=current_recipe,
                recipe_list=ref_recipe_list,
                queue=recipe_queue,
            )
            self._process_ingredient_list(
                menu_recipe=current_recipe, ingredient_list=ingredient_list
            )

            # TODO somehow get back to a Google Drive doc
            if error_list:
                response["has_error"] = True
                response["errors"][current_recipe["item"]] = error_list
                self.has_errors = True
                cprint("\t" + "\n\t".join(error_list), "green")

        return response

    def _add_to_grocery_list_raw(
        self,
        quantity: float,
        ingredient: Ingredient,
        from_recipe: str,
        for_day: date,
    ):
        if self.grocery_list_raw is None:
            self.grocery_list_raw = pd.DataFrame()

        # TODO if series in future, can simplify
        new_entry = pd.DataFrame(
            {
                "quantity": quantity,
                # TODO do we need unit?
                "unit": ingredient.unit,
                "pint_unit": ingredient.pint_unit,
                # TODO already add to Ingredient when first created?
                "dimension": str(ingredient.pint_unit.dimensionality)
                if ingredient.pint_unit
                else None,
                "item": ingredient.item,
                "is_staple": ingredient.is_staple,
                "is_optional": ingredient.is_optional,
                "food_group": ingredient.group,
                "item_plural": ingredient.item_plural,
                "store": ingredient.store,
                "barcode": ingredient.barcode,
                "from_recipe": from_recipe,
                "for_day": for_day,
                "for_day_str": for_day.strftime("%a"),
                "shopping_date": self._get_shopping_day(
                    for_day=for_day, food_group=ingredient.group
                ),
            },
            index=[0],
        )

        self.grocery_list_raw = pd.concat(
            [self.grocery_list_raw, new_entry], ignore_index=True
        )

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
        self,
        menu_recipe: pd.Series,
        recipe_list: List[Recipe],
        queue: List[pd.Series],
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
            due_date = self.due_date_formatter.get_date_relative_to_anchor(
                weekday=day
            ).date()

            meal_time = None
            meal_times = MealTime.name_list("lower")
            while meal_time not in meal_times:
                meal_time = input(f"\nMealtime {meal_times}: ").lower()

            days_back = 0
            if due_date > menu_recipe.for_day:
                days_back = 7

            return self.due_date_formatter.set_date_with_meal_time(
                due_date=due_date, meal_time=meal_time
            ) - timedelta(days=days_back)

        def _give_referenced_recipe_details(recipe: Recipe):
            total_factor = menu_recipe.eat_factor + menu_recipe.freeze_factor
            print("\n#### REFERENCED RECIPE CHECK ####")
            print(f"- from recipe: {menu_recipe.recipe.title}")
            print(f"-- total_factor: {total_factor}")
            print(f"-- for day: {menu_recipe.for_day.strftime('%a')}")
            print(f"- referenced recipe: {recipe.title}")
            print(f"-- amount needed: {recipe.amount}")
            print(f"-- total time: {recipe.time_total}")

        for ref_recipe in recipe_list:

            # TODO make more robust to other methods
            if (
                self.config.run_mode.with_todoist
                and self.config.run_mode.check_referenced_recipe
            ):
                _give_referenced_recipe_details(recipe=ref_recipe)
                # TODO would be ideal if could guess to
                #  make ahead like beans; should just add if we need to make
                if _check_yes_no(f"Need to make '{ref_recipe.title}'?") == "Y":
                    ref_menu_recipe = menu_recipe.copy()
                    ref_menu_recipe["from_recipe"] += f"{ref_recipe.title}"
                    ref_menu_recipe["eat_factor"] *= ref_recipe.factor
                    ref_menu_recipe["freeze_factor"] *= ref_recipe.factor
                    ref_menu_recipe["recipe"] = ref_recipe
                    queue.append(ref_menu_recipe)

                    if (
                        ref_recipe.time_total is None
                        or ref_recipe.time_total > timedelta(minutes=20)
                    ):
                        # TODO simplify to day before at dessert or override?
                        if (
                            _check_yes_no(
                                f"Separately schedule '{ref_recipe.title}'?"
                            )
                            == "Y"
                        ):
                            self._add_preparation_task_to_queue(
                                f"[PREP] {ref_recipe.amount}",
                                due_date=_get_schedule_day_hour_minute(),
                                from_recipe=[ref_menu_recipe.from_recipe],
                                for_day_str=[
                                    menu_recipe.for_day.strftime("%a")
                                ],
                            )

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

    def _format_ingredient_str(self, entry: pd.Series) -> str:
        item = entry["item"]
        if entry["quantity"] > 1 or not pd.isnull(entry["pint_unit"]):
            item = entry["item_plural"]
        if (
            "aisle_group" in entry.keys()
            and entry["aisle_group"] in self.config.store_to_specialty_list
        ):
            item = f"[{entry['aisle_group']}] {item}"

        ingredient_str = "{item}, {quantity}".format(
            item=item, quantity=convert_number_to_str(entry.quantity)
        )

        # TODO: do we need .unit anymore?
        if not pd.isnull(entry.pint_unit):
            unit_str = self.unit_formatter.get_unit_str(
                entry["quantity"], entry["pint_unit"]
            )
            ingredient_str += f" {unit_str}"

        if entry.is_optional:
            ingredient_str += " (optional)"

        return ingredient_str

    def _get_shopping_day(self, for_day: date, food_group: str) -> date:
        if (
            self.secondary_shopping_date
            and (for_day >= self.secondary_shopping_date)
            and (food_group.casefold() in self.second_shopping_day_group)
        ):
            return self.secondary_shopping_date
        return self.primary_shopping_date

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
            due_date=self.due_date_formatter.set_date_with_meal_time(
                due_date=row.for_day
                - timedelta(days=config_bean_prep.prep_day),
                meal_time=config_bean_prep.prep_meal,
            ),
            from_recipe=row.from_recipe,
            for_day_str=[row.for_day.strftime("%a")],
        )
        return row

    def _override_aisle_group_when_not_default_store(self, row):
        # if pantry item not found, store not set
        if row.store:
            if row.store.casefold() != self.config.default_store.casefold():
                return row.store
        return row.aisle_group

    def _process_ingredient_list(
        self, menu_recipe: pd.Series, ingredient_list: List[Ingredient]
    ):
        for ingredient in ingredient_list:
            recipe_factor = menu_recipe.eat_factor + menu_recipe.freeze_factor
            self._add_to_grocery_list_raw(
                quantity=ingredient.quantity * recipe_factor,
                ingredient=ingredient,
                from_recipe=menu_recipe.from_recipe,
                for_day=menu_recipe.for_day,
            )
