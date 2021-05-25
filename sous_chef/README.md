# Sous Chef

## Setup
1. Run `update_env.sh`.
2. Run `pre-commit install`.

## Manual configuration
The paths and user information come from the argparser. The default settings 
are below. Beware that optional parameters for the sections 'menu' or 'grocery_list'
have to be specified on the command line after the section, while general
optional parameters are specified before.

### Menu
The menu is created and sent in a json file via email to the configured recipients.

### Grocery list
Using the menu json, a grocery list is manually created.  
**_TODO_** Add details.

### Weekly template
A yml file outlining the weekly food plan is in menu_template. For each desired
cooking day, a task entry should be added that looks like this:
```yaml
- Saturday:
    max_active_time: -1
    # time that you would like to eat dinner
    eat_time: "18:00"
    # each meal, for now, is based around a protein source. these
    protein_source: beef
    servings: 4
    recipe_previously_tried: 0
```
* **max_active_time** -- max. time to cook. Currently, this is based on the total 
time of a recipe, but in future iterations, this should be the active time (cooking or preparation).
* **eat_time** - local time when you would like to eat dinner. This is currently 
_NOT_ used, but the idea is to create Todoist tasks or another reminder for 
preparation steps (defrosting, marinating, and even when to start cooking).
* **protein_source** -- for now, the main goal in creating a meal is designating
a protein source (vegetables & healthy starches are also important).
  * options include: `beef`, `unspecified`, `non-flesh`, `seafood`, `poultry
  `, `pork`, which are mapped in the filter_recipes.py
* **servings** -- indicates how many average people should be fed by the meal. In 
the future, this should be a scalable factor, which depends on the number of family
members given in the argparser. This is currently _NOT_ used and would be used to 
scale recipes values to the needed quantity.
* **recipe_previously_tried** -- when active, requires a recipe to have a rating 
  * options: `0` (false) or `1` (true)

### Recipe data
Our sous chef works with [RecetteTek](https://www.recettetek.com/en/) formatted
json files. These come from exporting and un-packaging an RTK file. These files
should be placed in the recipe_data folder.

## Integrated services
#### Gmail API 
Used for sending emails:
* https://developers.google.com/gmail/api/quickstart/python
* https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send

#### Todoist
Create a `todoist_token.txt` file in the sub-directory sous_chef. Copy in your
Todoist API token, which is found in the web app at `Settings -> Integrations -> API token`.

Used for setting up tasks:
* https://developer.todoist.com/sync/v8/
* https://github.com/doist/todoist-python
* https://buildmedia.readthedocs.org/media/pdf/pytodoist/latest/pytodoist.pdf
