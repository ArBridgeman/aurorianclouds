# src/routes/visualizations.py


# router = APIRouter()
#
# def create_base64_encoded_image(fig):
#     """Convert matplotlib figure to base64 encoded string"""
#     buf = BytesIO()
#     fig.savefig(buf, format='png', bbox_inches='tight')
#     buf.seek(0)
#     string = base64.b64encode(buf.getvalue()).decode('utf-8')
#     plt.close(fig)  # Clean up memory
#     return string
#
# @router.get("/visualizations/stats/{stat_type}")
# async def get_recipe_stats(stat_type: str):
#     """Generate recipe statistics visualization using seaborn/matplotlib"""
#     df = await get_recipe_dataframe()
#
#     plt.style.use('seaborn')  # Set seaborn style
#     fig, ax = plt.subplots(figsize=(10, 6))
#
#     if stat_type == "ingredients":
#         # Count of ingredients across recipes
#         ingredient_counts = df['ingredients'].explode().value_counts()
#         sns.barplot(x=ingredient_counts.values, y=ingredient_counts.index, ax=ax)
#         ax.set_title('Most Common Ingredients')
#         ax.set_xlabel('Number of Recipes')
#
#     elif stat_type == "cooking_time":
#         # Distribution of cooking times
#         sns.histplot(data=df, x='cooking_time', ax=ax, kde=True)
#         ax.set_title('Distribution of Cooking Times')
#         ax.set_xlabel('Cooking Time (minutes)')
#
#     elif stat_type == "rating_distribution":
#         # Rating distribution
#         sns.boxplot(data=df, x='rating', ax=ax)
#         ax.set_title('Recipe Ratings Distribution')
#
#     else:
#         raise ValueError(f"Unknown stat_type: {stat_type}")
#
#     # Adjust layout and convert to base64
#     plt.tight_layout()
#     image_data = create_base64_encoded_image(fig)
#
#     return {"image": f"data:image/png;base64,{image_data}"}
#
# @router.get("/visualizations/correlation_matrix")
# async def get_correlation_matrix():
#     """Generate correlation matrix visualization"""
#     df = await get_recipe_dataframe()
#
#     # Select numerical columns for correlation
#     numeric_df = df.select_dtypes(include=[np.number])
#
#     plt.style.use('seaborn')
#     fig = plt.figure(figsize=(10, 8))
#
#     # Create correlation matrix
#     corr_matrix = numeric_df.corr()
#     sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0)
#     plt.title('Recipe Metrics Correlation Matrix')
#
#     # Convert to base64 and clean up
#     image_data = create_base64_encoded_image(fig)
#     return {"image": f"data:image/png;base64,{image_data}"}
#
# @router.get("/visualizations/recipe_trends")
# async def get_recipe_trends():
#     """Generate recipe trends visualization"""
#     df = await get_recipe_dataframe()
#
#     plt.style.use('seaborn')
#     fig, ax = plt.subplots(figsize=(12, 6))
#
#     # Create trend plot
#     sns.lineplot(data=df.sort_values('created_at'), x='created_at', y='rating', ax=ax)
#     ax.set_title('Recipe Rating Trends Over Time')
#     ax.set_xlabel('Date Created')
#     ax.set_ylabel('Average Rating')
#
#     # Convert to base64 and clean up
#     plt.tight_layout()
#     image_data = create_base64_encoded_image(fig)
#     return {"image": f"data:image/png;base64,{image_data}"}
#
# # Add visualization routes to main application
# from .routes.visualizations import router as visualizations_router
# app.include_router(visualizations_router, prefix="/api/v1")
