import pandas as pd
from sous_chef.grocery_list.generate_grocery_list._grocery_list_basic import (
    GroceryListBasic,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


class GroceryListAggregated(GroceryListBasic):
    def _aggregate_grocery_list(self):
        # do not drop nas, as some items are dimensionless (None)
        if self.grocery_list is None:
            self.grocery_list = pd.DataFrame()

        # TODO add for_day option

        # TODO fix pantry list to not do lidl for meats (real group instead)
        grouped = self.grocery_list_raw.groupby(
            ["item", "dimension", "shopping_date"], dropna=False
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
                shopping_date=("shopping_date", "first"),
            )
            .astype({"is_staple": bool, "barcode": str})
        )
        if self.config.ingredient_replacement.can_to_dried_bean.is_active:
            agg = agg.apply(self._override_can_to_dried_bean, axis=1)
        return agg

    def _transform_food_to_aisle_group(self, food_group: str):
        aisle_map = self.config.food_group_to_aisle_map
        # food_group may be none, particularly if pantry item not found
        if food_group and food_group.casefold() in aisle_map:
            return aisle_map[food_group.casefold()]
        return "Unknown"
