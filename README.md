[![codecov](https://codecov.io/gh/ArBridgeman/aurorianclouds/branch/main/graph/badge.svg?token=86JV74K4VY)](https://codecov.io/gh/ArBridgeman/aurorianclouds)
[![license](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

## Table of contents

- [Requirements](#requirements)
- [Projects](#projects)
  - [sous-chef](#sous-chef)
  - [utilities](#utilities)
  - [jellyfin-helpers](#jellyfin-helpers)
  - [banking-helpers](#banking-helpers)
- [Development tools](#development-tools)
  - [pre-commit](#pre-commit)
  - [just](#just)

## Requirements

- **Poetry:** >= 2.3.2, <3
- **Python:** >= 3.11, <4

Use separate virtual environments for each project when working from source.

These projects are currently developed and used directly from source. We do
not currently publish versioned releases or distribution packages; version
numbers in individual project metadata indicate development state only.

Project maturity labels describe the current level of confidence in each
project:

- **Established:** Actively developed, tested, and sufficiently stable for its
  intended use, although it may continue to evolve.
- **Experimental:** Early-stage software whose interfaces and implementation
  may change substantially as it is being developed and evaluated.

## Projects

### sous-chef

**Maturity: Established**

`sous-chef` is a meal-planning and recipe-management application. It parses prepared
recipes, creates menus, schedules menu items, and prepares an aisle-based grocery list.
Results are exported to services such as Todoist and Google Sheets. It is
the most established application in this repository and includes extensive
unit, integration, and end-to-end test coverage.

- **Documentation (private):** https://endymion.atlassian.net/wiki/spaces/SC/overview?homepageId=98430

See the [sous-chef source code](./sous-chef/).

### utilities

**Maturity: Established**

`utilities` is a shared Python library containing common functionality used by
the other projects. It provides reusable helpers for tasks such as enum
handling, input validation, Todoist integration, and Google Sheets access.
Both [sous-chef](./sous-chef/) and
[jellyfin-helpers](./jellyfin-helpers/) use it as an underlying dependency.

See the [utilities source code](./utilities/).

### jellyfin-helpers

**Maturity: Established**

`jellyfin-helpers` provides scripts and API helpers for working with media
libraries managed by Jellyfin. It can inspect library contents, interact with
Jellyfin playlists and metadata, and build workout plans from tagged workout
videos. It uses `utilities` for shared integrations and supporting helpers.

See the [jellyfin-helpers source code](./jellyfin-helpers/).

### banking-helpers

**Maturity: Experimental**

`banking-helpers` is a Streamlit application and command-line tool for
standardizing banking CSV exports. Bank-specific YAML configurations describe
input formats, after which transactions can be validated, normalized, and
exported as CSV or Excel files with useful dropdown validation. This project
is experimental and was initially produced with AI-generated code, so its
interfaces and implementation will change as it matures.

See the [banking-helpers README](./banking-helpers/README.md).

## Development tools

The repository provides a few tools to make common development tasks consistent
across projects.

### pre-commit

[`pre-commit`](https://pre-commit.com/) runs the configured formatting and
linting hooks before commits. The repository configuration is in
[`.pre-commit-config.yaml`](./.pre-commit-config.yaml).

Install the project dependencies, install the Git hook, and run the hooks once
against the entire repository:

```bash
poetry install
poetry run pre-commit install
```

After installation, the hooks run automatically when committing.


### just

[`just`](https://just.systems/man/en/) is the repository's command runner. Its
recipes are defined in [`justfile`](./justfile).

List the available recipes and run common checks with:

```bash
just --list
just <command>
```
