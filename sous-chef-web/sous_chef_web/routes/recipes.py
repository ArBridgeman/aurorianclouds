from fastapi import APIRouter
from sous_chef_web.utils import get_recipes

router = APIRouter()


@router.get("/recipes/")
async def get_recipes(
    category: str = None, cuisine_type: str = None, limit: int = 100
):
    """Get filtered recipes with optional category and cuisine filters"""
    df = await get_recipes()  # Your existing backend function

    # Apply filters
    filtered_df = df.copy()
    if category:
        filtered_df = filtered_df[filtered_df["category"] == category]
    if cuisine_type:
        filtered_df = filtered_df[filtered_df["cuisine_type"] == cuisine_type]

    return filtered_df.head(limit).to_dict("records")


@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str):
    """Get details of a specific recipe"""
    df = await get_recipes()
    recipe = df[df["id"] == recipe_id].iloc[0]
    return dict(recipe)
