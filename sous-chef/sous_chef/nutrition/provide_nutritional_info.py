from typing import Dict, List

from openfoodfacts import products
from pydantic import BaseModel


class Product(BaseModel):
    brands: str
    completeness: float
    nutriscore_grade: str
    product_name: str
    quantity: str
    level_fat: str
    level_salt: str
    level_saturated_fat: str
    level_sugars: str
    per_100g_carbohydrates: float
    per_100g_energy_kcal: float
    per_100g_fat: float
    per_100g_proteins: float
    per_100g_salt: float
    per_100g_saturated_fat: float
    per_100g_sugars: float


PRODUCT_FIELDS = Product.__dict__["__annotations__"].keys()
NUTRIENT_LEVEL_FIELDS = [
    key for key in PRODUCT_FIELDS if key.startswith("level_")
]
NUTRIMENT_FIELDS = [key for key in PRODUCT_FIELDS if key.startswith("per_100g")]
BASE_PRODUCT_FIELDS = list(
    set(PRODUCT_FIELDS) - set(NUTRIENT_LEVEL_FIELDS) - set(NUTRIMENT_FIELDS)
)


class Nutritionist:
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
            fields[attr] = base_dict[mod_attr + suffix_to_add]
        return fields

    def _extract_per_product(self, barcode: str) -> Product:
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

        return Product(**base_product, **nutrient_level, **nutriment)


# TODO export to gsheets
# TODO add test when re-syncing to check that values have not changed
