from __future__ import annotations

from types import SimpleNamespace

from wildmagic.scenes import menu_scene
from wildmagic.scenes.menu_scene import MenuScene


class Host(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(
            menu_active=True,
            menu_page="main",
            menu_cursor=0,
            menu_prev_page="main",
            ui_scale=2,
            menu_models=[],
            closed=False,
            scaled=False,
        )

    def _close_menu(self) -> None:
        self.closed = True
        self.menu_active = False

    def _toggle_ui_scale(self) -> None:
        self.scaled = True


def test_menu_scene_builds_main_items_from_host_state() -> None:
    host = Host()

    items = MenuScene(host).items()

    assert [item["action"] for item in items] == [
        "resume",
        "toggle_ui_scale",
        "config",
        "quit",
    ]
    assert items[1]["label"] == "UI Scale: 2x"


def test_menu_scene_cycle_updates_config_without_touching_disk(monkeypatch) -> None:
    host = Host()
    host.menu_cursor = 0
    scene = MenuScene(host)
    written: list[tuple[str, str]] = []
    spec = {
        "key": "TEST_KEY",
        "label": "Test",
        "type": "cycle",
        "values": ["a", "b", "c"],
        "default": "a",
    }

    monkeypatch.setattr(menu_scene, "get_config_value", lambda _key, _default: "b")
    monkeypatch.setattr(
        menu_scene, "set_config_value", lambda key, value: written.append((key, value))
    )

    scene.cycle([{"action": "config_item", "spec": spec}], +1)

    assert written == [("TEST_KEY", "c")]


def test_menu_scene_select_delegates_host_actions() -> None:
    host = Host()
    scene = MenuScene(host)

    scene.select([{"action": "toggle_ui_scale"}])
    assert host.scaled

    scene.select([{"action": "resume"}])
    assert host.closed


def test_menu_scene_select_opens_config_page() -> None:
    host = Host()

    MenuScene(host).select([{"action": "config"}])

    assert host.menu_prev_page == "main"
    assert host.menu_page == "config"
    assert host.menu_cursor == 0
