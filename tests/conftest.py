from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="run provider-sensitive or long-running tests and do not force mock background providers",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "full: long-running or provider-sensitive test")
    if not config.getoption("--full"):
        # The trim suite should not accidentally wait on a local LLM because a
        # developer's .env points background generation at Ollama.
        os.environ.setdefault("WILDMAGIC_TOWN_PROVIDER", "mock")
        os.environ.setdefault("WILDMAGIC_CANON_PREWARM_ENABLED", "0")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--full"):
        return
    skip_full = pytest.mark.skip(reason="requires pytest --full")
    for item in items:
        if "full" in item.keywords:
            item.add_marker(skip_full)
