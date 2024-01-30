"""Automatically configures DARA settings."""

from importlib.metadata import version

from dara.refine import do_refinement, do_refinement_no_saving
from dara.settings import DaraSettings

__version__ = version("dara")

SETTINGS = DaraSettings()
