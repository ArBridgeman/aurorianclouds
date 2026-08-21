set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# Show the available commands when `just` is run without a recipe.
default:
    @just --list

# Run all configured pre-commit hooks against the repository.
precommit:
    poetry run pre-commit run --all-files

# Audit GitHub Actions, Dependabot, and pre-commit configuration.
zizmor:
    poetry run zizmor .github .pre-commit-config.yaml

# Print the site-packages directory for a project's Poetry environment.
project-site-packages project:
    poetry -C '{{project}}' run python -c 'import sysconfig; print(sysconfig.get_path("purelib"))'

# Audit the packages installed in one project's environment.
# The pip-audit executable comes from the root Poetry environment; the
# --path argument points it at the selected project's installed packages.
pip-audit project:
    poetry -C '{{project}}' sync
    site_packages=$(just project-site-packages '{{project}}') && poetry run pip-audit --path "$site_packages"

# Audit all project environments.
pip-audit-all:
    just pip-audit sous-chef
    just pip-audit utilities
    just pip-audit jellyfin-helpers
    just pip-audit banking-helpers
