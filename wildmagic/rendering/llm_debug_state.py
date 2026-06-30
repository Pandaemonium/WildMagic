from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pygame

from wildmagic.rendering.layout import LLM_PANEL_WIDTH, WINDOW_HEIGHT

Color = tuple[int, int, int]
LlmLine = tuple[str, Color]


@dataclass
class LlmDebugState:
    """Mutable state owned by the LLM debug panel.

    The embedded panel and the optional pop-out window both render and interact
    with the same panel state. Keeping these fields together makes future panel
    changes less likely to drift between those two surfaces.
    """

    entries: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    seen: set[str] = field(default_factory=set)
    lines_cache: list[LlmLine] | None = None
    cache_sec: int = -1
    block_ranges: list[tuple[int, int]] = field(default_factory=list)
    entry_block_ranges: dict[int, dict[str, tuple[int, int]]] = field(
        default_factory=dict
    )
    call_button_rects: list[tuple[pygame.Rect, int]] = field(default_factory=list)
    selected_call_index: int | None = None
    selected_call_part: str = "response"
    scroll_offset: int = 0
    autoscroll: bool = True
    dragging_scrollbar: bool = False
    drag_grab_dy: int = 0
    content_rect: pygame.Rect = field(
        default_factory=lambda: pygame.Rect(0, 0, LLM_PANEL_WIDTH, WINDOW_HEIGHT)
    )
    scrollbar_track_rect: pygame.Rect | None = None
    scrollbar_thumb_rect: pygame.Rect | None = None
    max_scroll: int = 0
    line_rects: list[tuple[pygame.Rect, int]] = field(default_factory=list)
    selection_anchor: int | None = None
    selection_focus: int | None = None
    dragging_selection: bool = False

    @classmethod
    def create(cls) -> "LlmDebugState":
        return cls()

    def invalidate_lines(self) -> None:
        self.lines_cache = None

    def reset(self) -> None:
        fresh = type(self).create()
        self.__dict__.update(fresh.__dict__)


class LlmDebugHostAdapter:
    """Compatibility properties for hosts backed by ``LlmDebugState``."""

    llm_debug: LlmDebugState

    @property
    def llm_debug_entries(self) -> list[dict[str, Any]]:
        return self.llm_debug.entries

    @llm_debug_entries.setter
    def llm_debug_entries(self, value: list[dict[str, Any]]) -> None:
        self.llm_debug.entries = value

    @property
    def llm_debug_started_at(self) -> datetime:
        return self.llm_debug.started_at

    @llm_debug_started_at.setter
    def llm_debug_started_at(self, value: datetime) -> None:
        self.llm_debug.started_at = value

    @property
    def llm_debug_seen(self) -> set[str]:
        return self.llm_debug.seen

    @llm_debug_seen.setter
    def llm_debug_seen(self, value: set[str]) -> None:
        self.llm_debug.seen = value

    @property
    def _llm_lines_cache(self) -> list[LlmLine] | None:
        return self.llm_debug.lines_cache

    @_llm_lines_cache.setter
    def _llm_lines_cache(self, value: list[LlmLine] | None) -> None:
        self.llm_debug.lines_cache = value

    @property
    def _llm_cache_sec(self) -> int:
        return self.llm_debug.cache_sec

    @_llm_cache_sec.setter
    def _llm_cache_sec(self, value: int) -> None:
        self.llm_debug.cache_sec = value

    @property
    def llm_block_ranges(self) -> list[tuple[int, int]]:
        return self.llm_debug.block_ranges

    @llm_block_ranges.setter
    def llm_block_ranges(self, value: list[tuple[int, int]]) -> None:
        self.llm_debug.block_ranges = value

    @property
    def llm_entry_block_ranges(self) -> dict[int, dict[str, tuple[int, int]]]:
        return self.llm_debug.entry_block_ranges

    @llm_entry_block_ranges.setter
    def llm_entry_block_ranges(
        self, value: dict[int, dict[str, tuple[int, int]]]
    ) -> None:
        self.llm_debug.entry_block_ranges = value

    @property
    def llm_call_button_rects(self) -> list[tuple[pygame.Rect, int]]:
        return self.llm_debug.call_button_rects

    @llm_call_button_rects.setter
    def llm_call_button_rects(self, value: list[tuple[pygame.Rect, int]]) -> None:
        self.llm_debug.call_button_rects = value

    @property
    def llm_selected_call_index(self) -> int | None:
        return self.llm_debug.selected_call_index

    @llm_selected_call_index.setter
    def llm_selected_call_index(self, value: int | None) -> None:
        self.llm_debug.selected_call_index = value

    @property
    def llm_selected_call_part(self) -> str:
        return self.llm_debug.selected_call_part

    @llm_selected_call_part.setter
    def llm_selected_call_part(self, value: str) -> None:
        self.llm_debug.selected_call_part = value

    @property
    def llm_scroll_offset(self) -> int:
        return self.llm_debug.scroll_offset

    @llm_scroll_offset.setter
    def llm_scroll_offset(self, value: int) -> None:
        self.llm_debug.scroll_offset = value

    @property
    def llm_autoscroll(self) -> bool:
        return self.llm_debug.autoscroll

    @llm_autoscroll.setter
    def llm_autoscroll(self, value: bool) -> None:
        self.llm_debug.autoscroll = value

    @property
    def llm_dragging_scrollbar(self) -> bool:
        return self.llm_debug.dragging_scrollbar

    @llm_dragging_scrollbar.setter
    def llm_dragging_scrollbar(self, value: bool) -> None:
        self.llm_debug.dragging_scrollbar = value

    @property
    def llm_drag_grab_dy(self) -> int:
        return self.llm_debug.drag_grab_dy

    @llm_drag_grab_dy.setter
    def llm_drag_grab_dy(self, value: int) -> None:
        self.llm_debug.drag_grab_dy = value

    @property
    def llm_content_rect(self) -> pygame.Rect:
        return self.llm_debug.content_rect

    @llm_content_rect.setter
    def llm_content_rect(self, value: pygame.Rect) -> None:
        self.llm_debug.content_rect = value

    @property
    def llm_scrollbar_track_rect(self) -> pygame.Rect | None:
        return self.llm_debug.scrollbar_track_rect

    @llm_scrollbar_track_rect.setter
    def llm_scrollbar_track_rect(self, value: pygame.Rect | None) -> None:
        self.llm_debug.scrollbar_track_rect = value

    @property
    def llm_scrollbar_thumb_rect(self) -> pygame.Rect | None:
        return self.llm_debug.scrollbar_thumb_rect

    @llm_scrollbar_thumb_rect.setter
    def llm_scrollbar_thumb_rect(self, value: pygame.Rect | None) -> None:
        self.llm_debug.scrollbar_thumb_rect = value

    @property
    def _llm_max_scroll(self) -> int:
        return self.llm_debug.max_scroll

    @_llm_max_scroll.setter
    def _llm_max_scroll(self, value: int) -> None:
        self.llm_debug.max_scroll = value

    @property
    def llm_line_rects(self) -> list[tuple[pygame.Rect, int]]:
        return self.llm_debug.line_rects

    @llm_line_rects.setter
    def llm_line_rects(self, value: list[tuple[pygame.Rect, int]]) -> None:
        self.llm_debug.line_rects = value

    @property
    def llm_selection_anchor(self) -> int | None:
        return self.llm_debug.selection_anchor

    @llm_selection_anchor.setter
    def llm_selection_anchor(self, value: int | None) -> None:
        self.llm_debug.selection_anchor = value

    @property
    def llm_selection_focus(self) -> int | None:
        return self.llm_debug.selection_focus

    @llm_selection_focus.setter
    def llm_selection_focus(self, value: int | None) -> None:
        self.llm_debug.selection_focus = value

    @property
    def dragging_llm_selection(self) -> bool:
        return self.llm_debug.dragging_selection

    @dragging_llm_selection.setter
    def dragging_llm_selection(self, value: bool) -> None:
        self.llm_debug.dragging_selection = value
