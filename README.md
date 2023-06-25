[![codecov](https://codecov.io/gh/ArBridgeman/aurorianclouds/branch/main/graph/badge.svg?token=86JV74K4VY)](https://codecov.io/gh/ArBridgeman/aurorianclouds)
[![license](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

<!-- TOC -->
* [sous-chef](#sous-chef)
  * [API](#api)
  * [Testing](#testing)
<!-- TOC -->

# sous-chef
sous_chef is a Python application used to parse recipes to create grocery lists
& menus, which are exported to third-party APIs (i.e. Todoist).

Until recently, this has been solely a private project, and it is currently
under construction to make contributions more easily possible. We are working
on adding new features, while harmonizing the code base, adding much-needed 
tests, and creating some documentation.

- **Documentation (private):** https://endymion.atlassian.net/wiki/spaces/SC/overview?homepageId=98430
- **Source code:** https://github.com/ArBridgeman/aurorianclouds

## API
```bash
poetry run uvicorn sous_chef.api.main:app --reload
```

## Testing

Tests can then be run after installation with:
```bash
poetry run pytest sous_chef/unit_tests
```