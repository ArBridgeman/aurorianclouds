from hydra import compose, initialize
from omegaconf import DictConfig


def get_jellyfin_config() -> DictConfig:
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="jellyfin").jellyfin
