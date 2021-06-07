#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Catalog of useful definitions used within the other files.
#
#

INP_JSON_COLUMNS = {
    "title": str,
    "preparationTime": str,
    "cookingTime": str,
    "totalTime": str,
    "ingredients": str,
    "instructions": str,
    "rating": float,
    "favorite": bool,
    "categories": list,
    # TODO quantity should be split/standardized...it's bad!!!
    "quantity": str,
    "tags": list,
    "uuid": str,
}

CALENDAR_FILE_PATTERN = "calendar.json"

CALENDAR_COLUMNS = {"date": str, "title": str, "recipeUuid": str, "uuid": str}

TIME_UNITS = ["min", "minutes", "hour", "hours"]

DESIRED_MEAL_TIMES = {"morning": "8:00", "evening": "18:30"}

DAYS_OF_WEEK = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

PROTEIN_SOURCE = {
    "beef": ["beef"],
    "unspecified": [
        "beef",
        "seafood",
        "poultry",
        "plant protein",
        "milk protein",
        "egg",
        "pork",
    ],
    "non-flesh": ["plant protein", "milk protein", "egg"],
    "seafood": ["seafood"],
    "poultry": ["poultry"],
    "pork": ["pork"],
    "side_excluded": ["beef", "seafood", "poultry", "plant protein", "pork"],
}

ALLOWED_UNITS = [
    "cm",
    "m",
    "ccm",
    "cup",
    "can",
    "dimensionless",
    "drop",
    "gallon",
    "g",
    "inch",
    "kg",
    "l",
    "ml",
    "ounce",
    "pint",
    "pound-mass",
    "quart",
    "tbsp",
    "tsp",
    "package",
    "pkg",
    "pack",
    "jar",
]


RECIPE_FILE_PATTERN = "recipes*.json"

RTK_FILE_PATTERN = "backup*.rtk"
