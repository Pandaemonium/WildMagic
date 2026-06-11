"""Wild Magic, a tile roguelike prototype."""

from . import config as config

config.load_environment()

__all__ = ["config", "engine", "wild_magic", "ui"]
