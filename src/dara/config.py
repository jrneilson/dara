import os
from pathlib import Path
from types import MappingProxyType as FrozenDict
from typing import Any, Dict

import toml
from monty.design_patterns import singleton


def freeze_config(config_: Dict[str, Any]) -> FrozenDict:
    """
    Convert the config dict to frozen config.

    Args:
        config_: the dict of config data

    Returns
    -------
        frozen_config, which can not be modified
    """

    def _frozen_collection(collection_or_element):
        """Convert a list to tuple, a dict to frozen_dict recursively."""
        if isinstance(collection_or_element, list):
            return tuple(
                _frozen_collection(element) for element in collection_or_element
            )
        if isinstance(collection_or_element, dict):
            return FrozenDict(
                {k: _frozen_collection(v) for k, v in collection_or_element.items()}
            )

        return collection_or_element

    return _frozen_collection(config_)


@singleton
class Config:
    """Class used for storing all the config data."""

    DEFAULT_CONFIG_PATH: Path = Path(__file__).parent / "config.toml"

    def __init__(self):
        """Load a immutable toml config file from `config_path`."""
        path = Path(os.environ.get("DARA_CONFIG", self.DEFAULT_CONFIG_PATH))
        try:
            with path.open("r", encoding="utf-8") as f:
                _config = toml.load(f)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Config file was not found at {path}."
                "Please set your computer's environment variable 'ALAB_CONFIG' to the path to the config file. In "
                "absence of this environment variable, we assume there is a file named config.toml in the current "
                "directory."
            ) from exc

        self._path = path
        self._config = freeze_config(_config)

    def __getitem__(self, item):
        """Get the config item."""
        return self._config.__getitem__(item)

    def __str__(self):
        """Get the string representation of the config."""
        return self._config.__repr__()

    def __repr__(self):
        """Get the string representation of the config."""
        return self.__str__()

    def __hash__(self):  # type: ignore
        """Get the hash of the config."""
        return self._config.__hash__()

    def get(self, item, default=None) -> Any:
        """Get the config item."""
        return self._config.get(item, default)

    def __contains__(self, item):
        """Check if the config contains the item."""
        return self._config.__contains__(item)

    @property
    def path(self) -> Path:
        """The absolute path to the config file."""
        return self._path
