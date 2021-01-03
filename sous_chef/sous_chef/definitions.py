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
    "tags": list,
    "uuid": str
}

CALENDAR_COLUMNS = {"date": str,
                    "title": str,
                    "recipeUuid": str,
                    "uuid": str}

TIME_UNITS = ["min", "minutes", "hour", "hours"]

PROTEIN_SOURCE = {
    "beef": ["beef"],
    "unspecified": ["beef", "seafood", "poultry", "plant protein", "milk protein",
                    "egg", "pork"],
    "non-flesh": ["plant protein", "milk protein", "egg"],
    "seafood": ["seafood"],
    "poultry": ["poultry"],
    "pork": ["pork"],
    "side_excluded": ["beef", "seafood", "poultry", "plant protein", "pork"],
}
