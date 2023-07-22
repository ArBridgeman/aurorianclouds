from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from omegaconf import DictConfig
from openfoodfacts import products
from pydantic import BaseModel, ValidationError
from sous_chef.abstract.pandas_util import (
    are_shared_df_entries_identical,
    find_column_intersection,
)
from sous_chef.pantry_list.read_pantry_list import PantryList
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

FILE_LOGGER = get_logger(__name__)


class Product(BaseModel):
    barcode: str
    group: str
    pantry_ingredient: str
    product_name: str
    quantity: str
    brands: str
    completeness: float
    nutriscore_grade: Optional[str]
    level_fat: Optional[str]
    level_salt: Optional[str]
    level_saturated_fat: Optional[str]
    level_sugars: Optional[str]
    per_100g_carbohydrates: float
    per_100g_energy_kcal: float
    per_100g_fat: float
    per_100g_fiber: Optional[float]
    per_100g_proteins: float
    per_100g_salt: float
    per_100g_saturated_fat: float
    per_100g_sugars: float


PRODUCT_FIELDS = Product.__dict__["__annotations__"].keys()
PANTRY_FIELDS = ["barcode", "group", "pantry_ingredient"]
NUTRIENT_LEVEL_FIELDS = [
    key for key in PRODUCT_FIELDS if key.startswith("level_")
]
NUTRIMENT_FIELDS = [key for key in PRODUCT_FIELDS if key.startswith("per_100g")]
BASE_PRODUCT_FIELDS = list(
    set(PRODUCT_FIELDS)
    - set(NUTRIENT_LEVEL_FIELDS)
    - set(NUTRIMENT_FIELDS)
    - set(PANTRY_FIELDS)
)


@dataclass
class Nutritionist:
    config: DictConfig

    @staticmethod
    def _extract_fields(
        base_dict: Dict,
        list_to_extract: List[str],
        prefix_to_remove: str = "",
        suffix_to_add: str = "",
    ) -> Dict:
        fields = {}
        for attr in list_to_extract:
            mod_attr = attr.replace(prefix_to_remove, "")
            if mod_attr in ("saturated_fat", "energy_kcal"):
                mod_attr = mod_attr.replace("_", "-")
            fields[attr] = base_dict.get(mod_attr + suffix_to_add)
        return fields

    def _extract_per_product(
        self, barcode: str, group: str, pantry_ingredient: str
    ) -> Product:
        result = products.get_product(barcode)
        if result["status_verbose"] != "product found":
            raise ValueError

        product = result.pop("product")
        base_product = self._extract_fields(product, BASE_PRODUCT_FIELDS)
        nutrient_level = self._extract_fields(
            product["nutrient_levels"],
            NUTRIENT_LEVEL_FIELDS,
            prefix_to_remove="level_",
        )
        nutriment = self._extract_fields(
            product["nutriments"],
            NUTRIMENT_FIELDS,
            prefix_to_remove="per_100g_",
            suffix_to_add="_100g",
        )
        # TODO resolve barcode issue in pantry list
        # need to add ' to barcode so that gsheets write keeps as str
        return Product(
            **base_product,
            **nutrient_level,
            **nutriment,
            barcode=f"'{barcode}",
            group=group,
            pantry_ingredient=pantry_ingredient,
        )

    def _get_pantry_nutrition(self, pantry_list: PantryList) -> pd.DataFrame:
        new_nutrition_list = []
        for _, row in pantry_list.basic_pantry_list.iterrows():
            if not row.barcode:
                continue
            try:
                product = self._extract_per_product(
                    barcode=row.barcode,
                    group=row.group,
                    pantry_ingredient=row.ingredient,
                ).dict()
                new_nutrition_list.append(product)
            except ValidationError as err:
                FILE_LOGGER.error(
                    "[_get_pantry_list_products]",
                    ingredient=row.ingredient,
                    barcode=row.barcode,
                    warn=str(err),
                )
        return pd.DataFrame(new_nutrition_list)

    def get_pantry_nutrition_from_gsheets(self, gsheets_helper: GsheetsHelper):
        return gsheets_helper.get_worksheet(
            workbook_name=self.config.workbook_name,
            worksheet_name=self.config.sheet_name,
        )

    def sync_pantry_nutrition_to_gsheets(
        self,
        pantry_list: PantryList,
        gsheets_helper: GsheetsHelper,
        override_value: bool = False,
    ):
        new_nutrition_df = self._get_pantry_nutrition(pantry_list)
        write_df = new_nutrition_df

        shared_column = "barcode"
        if not override_value:
            saved_nutrition_df = self.get_pantry_nutrition_from_gsheets(
                gsheets_helper
            )
            if saved_nutrition_df.shape[
                0
            ] > 0 and not are_shared_df_entries_identical(
                orig_df=saved_nutrition_df,
                new_df=new_nutrition_df,
                shared_column=shared_column,
            ):
                shared_values = find_column_intersection(
                    df1=saved_nutrition_df,
                    df2=new_nutrition_df,
                    column=shared_column,
                )

                mask_new_df = ~new_nutrition_df[shared_column].isin(
                    shared_values
                )  # only new entries
                mask_saved_df = saved_nutrition_df[shared_column].isin(
                    shared_values
                )  # keep old entries
                write_df = pd.concat(
                    [
                        new_nutrition_df.loc[mask_new_df],
                        saved_nutrition_df.loc[mask_saved_df],
                    ]
                )

        gsheets_helper.write_worksheet(
            df=write_df,
            workbook_name=self.config.workbook_name,
            worksheet_name=self.config.sheet_name,
        )
