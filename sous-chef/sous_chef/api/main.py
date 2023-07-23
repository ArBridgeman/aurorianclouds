from fastapi import FastAPI

from .routers import grocery_list

app = FastAPI()

app.include_router(grocery_list.router)
