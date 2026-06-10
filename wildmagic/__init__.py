"""Wild Magic, a tile roguelike prototype."""

from dotenv import load_dotenv

load_dotenv()  # Loads .env but does NOT override existing shell environment variables.

__all__ = ["engine", "wild_magic", "ui"]
