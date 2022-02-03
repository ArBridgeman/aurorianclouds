sous_chef is a Python application used to parse recipes to create grocery lists
& menus, which are exported to third-party APIs (i.e. Todoist).

Until recently, this has been solely a private project, and it is currently
under construction to make contributions more easily possible. We are working
on adding new features, while harmonizing the code base, adding much-needed 
tests, and creating some documentation.

- **Documentation (private):** https://endymion.atlassian.net/wiki/spaces/SC/overview?homepageId=98430
- **Source code:** https://github.com/ArBridgeman/aurorianclouds

Testing:

sous_chef requires `poetry` and several packages defined in the `poetry.toml`
Tests can then be run after installation with:
```
poetry run pytest sous_chef/unit_tests
```