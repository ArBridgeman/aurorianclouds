from fastapi import APIRouter
from hydra import compose, initialize
from omegaconf import OmegaConf
from sous_chef.grocery_list.main import run_grocery_list

router = APIRouter()


@router.get("/grocery_list/config")
def check_config():
    config = _load_config()
    return OmegaConf.to_container(config)


@router.get("/grocery_list/run")
def run(debug: bool = True):
    config = _load_config()
    config.grocery_list.run_mode.with_todoist = not debug
    return run_grocery_list(config).to_json()


def _load_config():
    with initialize(version_base=None, config_path="../../../config"):
        return compose(config_name="grocery_list")
