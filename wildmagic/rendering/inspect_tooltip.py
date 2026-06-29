from __future__ import annotations

from typing import Any

import pygame

from wildmagic.models import TILE_NAMES, TILE_TAGS
from wildmagic.rendering.layout import (
    MAP_OFFSET_X,
    TILE_SIZE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from wildmagic.rendering.theme import (
    ACCENT,
    DANGER,
    GOLD,
    MUTED,
    PANEL_EDGE,
    TEXT,
    wrap_text,
)


def draw_inspect_tooltip(host: Any) -> None:
    """Draw the map-tile inspection tooltip and update its clickable command rects."""
    tx, ty = host.inspect_tile
    engine = host.engine
    state = engine.state

    if not engine.is_explored(tx, ty):
        host.inspect_tile = None
        return

    lines: list[tuple[str, tuple[int, int, int]]] = []

    # Tile
    tile = state.tiles[ty][tx]
    tile_name = TILE_NAMES.get(tile, tile).title()
    base_tags = sorted(TILE_TAGS.get(tile, set()))
    dyn_tags = list(state.tile_tags.get(f"{tx},{ty}", []))
    all_tags = base_tags + [tag for tag in dyn_tags if tag not in set(base_tags)]
    lines.append((f"[{tile}] {tile_name}", ACCENT))
    if all_tags:
        lines.append(("  " + ", ".join(all_tags), MUTED))
    room = engine.room_profile_at(tx, ty)
    if room is not None:
        lines.append((f"  {room.room_type} - {room.era}, {room.condition}", TEXT))
        topics = ", ".join(room.topics[:2])
        if topics:
            lines.append((f"  {topics}", MUTED))

    # Entities
    buttons: list[tuple[int, str]] = []
    player = state.player

    def detail_summary(entity_id: str) -> str | None:
        for tier in ("close", "far"):
            record = state.canon_records.get(f"canon_detail_{entity_id}_{tier}")
            if record is not None and record.summary:
                return record.summary
        return None

    visible = engine.is_visible(tx, ty)
    for entity in sorted(state.entities.values(), key=lambda item: item.id):
        if entity.x != tx or entity.y != ty:
            continue
        if not entity.alive and entity.kind not in {"item", "prop"}:
            continue
        if (
            not visible
            and "revealed" not in entity.statuses
            and entity.id != state.player_id
        ):
            continue

        lines.append(("", MUTED))

        if entity.kind == "prop":
            lines.append((f"[{entity.char}] {entity.name.title()}", GOLD))
            if "book" in entity.tags:
                # Books show their materialized title (the name above) and, once
                # read/prewarmed, their summary — never the verbose grammar
                # placeholder. Until the title call lands, say so.
                if not entity.details.get("title_materialized"):
                    lines.append(("  You can't read the title yet.", MUTED))
                if entity.details.get("summary_materialized") and entity.description:
                    for part in wrap_text(entity.description, 34):
                        lines.append((f"  {part}", TEXT))
            elif entity.description:
                for part in wrap_text(entity.description, 34):
                    lines.append((f"  {part}", TEXT))
            if entity.tags:
                lines.append(("  " + ", ".join(sorted(entity.tags)), MUTED))

        elif entity.kind == "item":
            lines.append((f"[{entity.char}] {entity.name.title()}", GOLD))
            details = [part for part in [entity.item_type, entity.material] if part]
            if details:
                lines.append(("  " + ", ".join(details), TEXT))
            if entity.tags:
                lines.append(("  " + ", ".join(sorted(entity.tags)), MUTED))

        elif entity.id == state.player_id:
            lines.append((f"[{entity.char}] You", (246, 240, 200)))
            lines.append(
                (
                    f"  HP {entity.hp}/{entity.max_hp}  MP {entity.mana}/{entity.max_mana}",
                    TEXT,
                )
            )
            if entity.statuses:
                status_str = ", ".join(
                    entity.status_display.get(key, key)
                    for key in sorted(entity.statuses)
                )
                for part in wrap_text(status_str, 34):
                    lines.append((f"  {part}", MUTED))

        elif entity.kind == "npc":
            profile = state.npc_profiles.get(entity.id)
            role_str = f" — {profile.role}" if profile and profile.role else ""
            lines.append((f"[{entity.char}] {entity.name}{role_str}", ACCENT))
            lines.append(
                (f"  HP {entity.hp}/{entity.max_hp}  [{entity.faction}]", TEXT)
            )
            if profile and profile.appearance:
                for part in wrap_text(profile.appearance, 34):
                    lines.append((f"  {part}", TEXT))

        else:
            entity_color = (
                DANGER
                if entity.faction == "enemy"
                else ACCENT
                if entity.faction == "ally"
                else TEXT
            )
            lines.append((f"[{entity.char}] {entity.name}", entity_color))
            lines.append(
                (f"  HP {entity.hp}/{entity.max_hp}  [{entity.faction}]", TEXT)
            )
            if entity.statuses:
                status_str = ", ".join(
                    entity.status_display.get(key, key)
                    for key in sorted(entity.statuses)
                )
                for part in wrap_text(status_str, 34):
                    lines.append((f"  {part}", MUTED))
            if entity.tags:
                lines.append(("  " + ", ".join(sorted(entity.tags)), MUTED))

        # Learned canon and study/read affordances for everything but you.
        if entity.id != state.player_id:
            summary = detail_summary(entity.id)
            if summary:
                for part in wrap_text(summary, 34):
                    lines.append((f"  {part}", (150, 170, 150)))
            distance = max(abs(entity.x - player.x), abs(entity.y - player.y))
            if entity.kind == "npc" and "bound" in entity.tags and distance <= 1:
                buttons.append((len(lines), "free"))
                lines.append(("  [ Free ]", (130, 185, 225)))
            if entity.kind == "npc":
                profile = state.npc_profiles.get(entity.id)
                if profile is not None and profile.wares:
                    buttons.append((len(lines), f"wares {entity.id}"))
                    lines.append(("  [ Wares ]", (130, 185, 225)))
            if entity.kind == "prop" and "book" in entity.tags and distance <= 1:
                buttons.append((len(lines), f"read {entity.name}"))
                lines.append(("  [ Read ]", (130, 185, 225)))
            buttons.append((len(lines), f"investigate {entity.id}"))
            lines.append(("  [ Investigate ]", (130, 185, 225)))

    # Targeting affordance: mark this square or clear it if already marked.
    lines.append(("", MUTED))
    if (state.target_x, state.target_y) == (tx, ty):
        buttons.append((len(lines), "untarget"))
        lines.append(("  [ Clear target ]", (225, 175, 130)))
    else:
        buttons.append((len(lines), f"target {tx} {ty}"))
        lines.append(("  [ + Target this ]", (130, 185, 225)))

    if not lines:
        host.inspect_button_rects = []
        return

    pad = 12
    tooltip_w = 310
    line_h = host.small_font.get_linesize() + 2
    total_h = pad * 2 + sum(4 if text == "" else line_h for text, _ in lines)

    tile_px = MAP_OFFSET_X + tx * TILE_SIZE
    tile_py = ty * TILE_SIZE
    bx = tile_px + TILE_SIZE + 4
    by = tile_py

    if bx + tooltip_w > WINDOW_WIDTH:
        bx = tile_px - tooltip_w - 4
    if by + total_h > WINDOW_HEIGHT:
        by = WINDOW_HEIGHT - total_h
    if by < 0:
        by = 0

    pygame.draw.rect(
        host.screen, (20, 22, 30), (bx, by, tooltip_w, total_h), border_radius=6
    )
    pygame.draw.rect(
        host.screen, PANEL_EDGE, (bx, by, tooltip_w, total_h), 1, border_radius=6
    )

    button_commands = dict(buttons)
    host.inspect_button_rects = []
    cy = by + pad
    for index, (text, color) in enumerate(lines):
        if text == "":
            cy += 4
            continue
        surf = host.small_font.render(text, True, color)
        host.screen.blit(surf, (bx + pad, cy))
        command = button_commands.get(index)
        if command:
            rect = pygame.Rect(bx + pad, cy - 1, surf.get_width() + 8, line_h)
            pygame.draw.rect(host.screen, (70, 95, 120), rect, 1, border_radius=4)
            host.inspect_button_rects.append((rect, command))
        cy += line_h
