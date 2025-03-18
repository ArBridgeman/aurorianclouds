import argparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Mount static files
app.mount(
    "/static", StaticFiles(directory="sous_chef_web/static/"), name="static"
)
#
# Initialize templates
templates = Jinja2Templates(directory="sous_chef_web/templates/")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Recipe visualization server")
    parser.add_argument(
        "--host", type=str, default="localhost", help="host to bind to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="port to bind to"
    )
    parser.add_argument(
        "--reload", action="store_true", help="enable auto-reload"
    )
    return parser.parse_args()


def start():
    """Main entry point for running the application"""
    args = parse_args()

    # Configure logging
    print(f"\nStarting server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {'Enabled' if args.reload else 'Disabled'}\n")

    # Run the application
    uvicorn.run(
        "sous_chef_web.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=1,  # Use 1 worker for development
    )


@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    """Welcome page route handler"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "page": {
                "title": "Recipe Library",
                "subtitle": "Your personal cookbook companion",
                "cta_text": "Start Exploring",
                "features": [
                    {
                        "icon": "utensils-crossed",
                        "title": "Recipe Management",
                        "description": "Organize and maintain your recipes",
                    },
                    {
                        "icon": "chart-bar",
                        "title": "Data Analytics",
                        "description": "Visualize your cooking patterns",
                    },
                    {
                        "icon": "filter",
                        "title": "Smart Filtering",
                        "description": "Find recipes quickly",
                    },
                ],
                "stats": [
                    {"label": "Recipes", "value": "150+"},
                    {"label": "Categories", "value": "20"},
                    {"label": "Ingredients", "value": "500+"},
                ],
            },
        },
    )


if __name__ == "__main__":
    start()
