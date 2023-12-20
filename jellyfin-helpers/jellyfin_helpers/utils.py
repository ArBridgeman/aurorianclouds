from hydra import compose, initialize
from omegaconf import DictConfig


def get_config(config_name: str) -> DictConfig:
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name=config_name)
