from __future__ import annotations

import os
import textwrap

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from .actions import GameSession
from .models import (
    DOOR,
    FIRE,
    FLOOR,
    ICE_WALL,
    MIST,
    OPEN_DOOR,
    POISON_CLOUD,
    RUBBLE,
    SLICK_ICE,
    STAIRS_DOWN,
    STAIRS_UP,
    VINES,
    WALL,
    WATER,
    Entity,
)


TILE_SIZE = 18
MAP_PIXEL_WIDTH = 42 * TILE_SIZE
MAP_PIXEL_HEIGHT = 28 * TILE_SIZE
PANEL_WIDTH = 430
WINDOW_WIDTH = MAP_PIXEL_WIDTH + PANEL_WIDTH
WINDOW_HEIGHT = 720
BACKGROUND = (13, 14, 18)
PANEL = (27, 29, 34)
PANEL_EDGE = (62, 66, 76)
TEXT = (224, 223, 214)
MUTED = (151, 153, 160)
ACCENT = (120, 202, 174)
SELECTED = (58, 90, 112)
DANGER = (232, 105, 85)
MANA = (102, 168, 255)
GOLD = (224, 177, 92)

TILE_COLORS = {
    FLOOR: (77, 80, 88),
    WALL: (123, 127, 140),
    DOOR: (176, 122, 74),
    OPEN_DOOR: (154, 126, 91),
    STAIRS_DOWN: (214, 190, 112),
    STAIRS_UP: (214, 190, 112),
    WATER: (70, 145, 195),
    FIRE: (232, 96, 70),
    SLICK_ICE: (156, 210, 224),
    ICE_WALL: (151, 220, 232),
    POISON_CLOUD: (144, 196, 84),
    VINES: (83, 170, 108),
    RUBBLE: (138, 120, 102),
    MIST: (170, 178, 185),
}

ENTITY_COLORS = {
    "player": (246, 240, 200),
    "enemy": (232, 115, 100),
    "ally": (120, 202, 174),
    "neutral": (190, 190, 190),
    "item": (230, 190, 92),
}


class GameUI:
    def __init__(self) -> None:
        pygame.init()
        pygame.key.set_repeat(350, 35)
        pygame.display.set_caption("Wild Magic")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.tile_font = pygame.font.SysFont("consolas", 20, bold=True)
        self.ui_font = pygame.font.SysFont("consolas", 17)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.session = GameSession()
        self.engine = self.session.engine
        self.input_text = ""
        self.input_active = True
        self.provider_label = self.session.provider_label
        self.log_line_rects: list[tuple[pygame.Rect, str]] = []
        self.log_selection_anchor: int | None = None
        self.log_selection_focus: int | None = None
        self.dragging_log_selection = False
        self.log_area = pygame.Rect(MAP_PIXEL_WIDTH + 20, 0, PANEL_WIDTH - 40, 0)
        self.spell_box_rect = pygame.Rect(MAP_PIXEL_WIDTH + 20, WINDOW_HEIGHT - 92, PANEL_WIDTH - 40, 54)

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in {pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION}:
                    self.handle_mouse(event)
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event)
            self.draw()
            pygame.display.flip()
            self.clock.tick(30)
        pygame.quit()

    def handle_key(self, event: pygame.event.Event) -> None:
        if event.mod & pygame.KMOD_CTRL:
            if event.key == pygame.K_c:
                self.copy_log_selection()
                return
            if event.key == pygame.K_a and self.log_line_rects:
                self.log_selection_anchor = 0
                self.log_selection_focus = len(self.log_line_rects) - 1
                return

        if event.key == pygame.K_r and self.engine.state.game_over:
            self.restart_run()
            return

        if event.key == pygame.K_ESCAPE:
            if self.input_text:
                self.input_text = ""
                self.input_active = True
            else:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        if self.input_active:
            if event.key == pygame.K_RETURN:
                self.cast_input_spell()
                return
            if event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return
            if event.key == pygame.K_TAB:
                self.input_active = False
                return
            if event.unicode and event.unicode.isprintable() and len(self.input_text) < 120:
                self.input_text += event.unicode
                return

        if event.key in {pygame.K_SLASH, pygame.K_RETURN}:
            self.input_active = True
            return
        if event.key in {pygame.K_UP, pygame.K_w, pygame.K_k, pygame.K_KP8}:
            self.session.execute_command("move north")
        elif event.key in {pygame.K_DOWN, pygame.K_s, pygame.K_j, pygame.K_KP2}:
            self.session.execute_command("move south")
        elif event.key in {pygame.K_LEFT, pygame.K_a, pygame.K_h, pygame.K_KP4}:
            self.session.execute_command("move west")
        elif event.key in {pygame.K_RIGHT, pygame.K_d, pygame.K_l, pygame.K_KP6}:
            self.session.execute_command("move east")
        elif event.key == pygame.K_KP7:
            self.session.execute_command("move northwest")
        elif event.key == pygame.K_KP9:
            self.session.execute_command("move northeast")
        elif event.key == pygame.K_KP1:
            self.session.execute_command("move southwest")
        elif event.key == pygame.K_KP3:
            self.session.execute_command("move southeast")
        elif event.key in {pygame.K_KP5}:
            self.session.execute_command("wait")
        elif event.key == pygame.K_GREATER or (event.key == pygame.K_PERIOD and event.mod & pygame.KMOD_SHIFT):
            self.session.execute_command("descend")
        elif event.key == pygame.K_LESS or (event.key == pygame.K_COMMA and event.mod & pygame.KMOD_SHIFT):
            self.session.execute_command("ascend")
        elif event.key == pygame.K_PERIOD:
            self.session.execute_command("wait")
        elif event.key == pygame.K_o:
            self.session.execute_command("open")
        elif event.key == pygame.K_g:
            self.session.execute_command("pickup")
        elif event.key == pygame.K_f:
            self.session.execute_command("spark")
        self.provider_label = self.session.provider_label

    def handle_mouse(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.spell_box_rect.collidepoint(event.pos):
                self.input_active = True
                self.dragging_log_selection = False
                self.log_selection_anchor = None
                self.log_selection_focus = None
                return
            index = self.log_line_index_at(event.pos)
            if index is not None:
                self.log_selection_anchor = index
                self.log_selection_focus = index
                self.dragging_log_selection = True
                self.input_active = False
            else:
                self.dragging_log_selection = False
            return
        if event.type == pygame.MOUSEMOTION and self.dragging_log_selection:
            index = self.log_line_index_at(event.pos)
            if index is not None:
                self.log_selection_focus = index
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_log_selection:
                index = self.log_line_index_at(event.pos)
                if index is not None:
                    self.log_selection_focus = index
            self.dragging_log_selection = False

    def restart_run(self) -> None:
        self.session = GameSession()
        self.engine = self.session.engine
        self.input_text = ""
        self.input_active = True
        self.provider_label = self.session.provider_label

    def log_line_index_at(self, pos: tuple[int, int]) -> int | None:
        if not self.log_area.collidepoint(pos):
            return None
        x, y = pos
        for index, (rect, _line) in enumerate(self.log_line_rects):
            expanded = rect.inflate(0, 4)
            expanded.x = self.log_area.x
            expanded.width = self.log_area.width
            if expanded.collidepoint(x, y):
                return index
        if self.log_line_rects:
            if y < self.log_line_rects[0][0].top:
                return 0
            if y > self.log_line_rects[-1][0].bottom:
                return len(self.log_line_rects) - 1
        return None

    def copy_log_selection(self) -> None:
        lines = self.selected_log_lines()
        if not lines:
            lines = [line for _rect, line in self.log_line_rects]
        if not lines:
            return
        text = "\n".join(lines)
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
            self.engine.state.add_message(f"Copied {len(lines)} log line(s).")
        except pygame.error:
            self.engine.state.add_message("Could not access the system clipboard.")

    def selected_log_lines(self) -> list[str]:
        if self.log_selection_anchor is None or self.log_selection_focus is None:
            return []
        start = max(0, min(self.log_selection_anchor, self.log_selection_focus))
        end = min(len(self.log_line_rects) - 1, max(self.log_selection_anchor, self.log_selection_focus))
        if start > end:
            return []
        return [line for _rect, line in self.log_line_rects[start : end + 1]]

    def cast_input_spell(self) -> None:
        spell = self.input_text.strip()
        if not spell:
            return
        self.input_text = ""
        self.input_active = True
        result = self.session.cast_wild(spell)
        if result.wild_magic:
            self.provider_label = str(result.wild_magic.get("provider") or self.session.provider_label)

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self.draw_map()
        self.draw_panel()

    def draw_map(self) -> None:
        state = self.engine.state
        for y, row in enumerate(state.tiles):
            for x, tile in enumerate(row):
                if not self.engine.is_explored(x, y):
                    continue
                color = TILE_COLORS.get(tile, TILE_COLORS[FLOOR])
                if not self.engine.is_visible(x, y):
                    color = dim_color(color)
                self.draw_glyph(tile, x, y, color)
        for entity in sorted(state.entities.values(), key=lambda item: item.kind == "player"):
            if not entity.alive and entity.kind == "item":
                continue
            revealed = "revealed" in entity.statuses
            visible = self.engine.is_visible(entity.x, entity.y)
            if entity.id != state.player_id and not visible and not revealed:
                continue
            color = self.entity_color(entity)
            if revealed and not visible:
                color = dim_color(color)
            self.draw_glyph(entity.char, entity.x, entity.y, color)

    def draw_glyph(self, glyph: str, x: int, y: int, color: tuple[int, int, int]) -> None:
        surface = self.tile_font.render(glyph, True, color)
        rect = surface.get_rect(center=(x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2))
        self.screen.blit(surface, rect)

    def entity_color(self, entity: Entity) -> tuple[int, int, int]:
        if entity.kind == "item":
            return ENTITY_COLORS["item"]
        base = ENTITY_COLORS.get(entity.faction, ENTITY_COLORS["neutral"])
        if not entity.alive:
            return base
        s = entity.statuses
        if "burning" in s:
            return blend_color(base, (232, 96, 70), 0.55)
        if "frozen" in s:
            return blend_color(base, (156, 210, 224), 0.55)
        if "poisoned" in s:
            return blend_color(base, (130, 200, 80), 0.55)
        if "bleeding" in s:
            return blend_color(base, (200, 60, 60), 0.4)
        if "invisible" in s:
            return blend_color(base, BACKGROUND, 0.65)
        return base

    def draw_panel(self) -> None:
        x = MAP_PIXEL_WIDTH
        pygame.draw.rect(self.screen, PANEL, (x, 0, PANEL_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(self.screen, PANEL_EDGE, (x, 0), (x, WINDOW_HEIGHT), 2)
        state = self.engine.state
        player = state.player
        cursor_y = 18
        cursor_y = self.draw_text("Wild Magic", x + 20, cursor_y, self.ui_font, ACCENT)
        cursor_y = self.draw_text(
            f"Turn {state.turn}  Depth {state.depth}/{state.max_depth}  Resolver {self.provider_label}",
            x + 20,
            cursor_y + 8,
            self.small_font,
            MUTED,
        )
        cursor_y = self.draw_bars(x + 20, cursor_y + 16, player)
        cursor_y = self.draw_statuses(x + 20, cursor_y + 10, player)
        cursor_y = self.draw_visible_enemies(x + 20, cursor_y + 8)
        cursor_y = self.draw_inventory(x + 20, cursor_y + 8)
        cursor_y = self.draw_floor_items(x + 20, cursor_y + 6)
        cursor_y = self.draw_curses(x + 20, cursor_y + 6)
        spell_height = self.spell_box_height()
        spell_y = WINDOW_HEIGHT - spell_height - 38
        log_y = cursor_y + 16
        log_height = max(120, spell_y - log_y - 38)
        self.draw_log(x + 20, log_y, log_height)
        self.draw_spell_box(x + 20, spell_y, spell_height)
        if state.game_over:
            overlay = pygame.Surface((MAP_PIXEL_WIDTH, MAP_PIXEL_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            big_font = pygame.font.SysFont("consolas", 48, bold=True)
            if state.victory:
                message = "YOU ESCAPED"
                color = ACCENT
            else:
                message = "YOU DIED"
                color = DANGER
            surface = big_font.render(message, True, color)
            rect = surface.get_rect(center=(MAP_PIXEL_WIDTH // 2, MAP_PIXEL_HEIGHT // 2))
            self.screen.blit(surface, rect)
            sub = pygame.font.SysFont("consolas", 18).render("Press R to restart", True, MUTED)
            sub_rect = sub.get_rect(center=(MAP_PIXEL_WIDTH // 2, MAP_PIXEL_HEIGHT // 2 + 50))
            self.screen.blit(sub, sub_rect)

    def draw_bars(self, x: int, y: int, player: Entity) -> int:
        y = self.draw_stat_bar(x, y, "HP", player.hp, player.max_hp, DANGER)
        y = self.draw_stat_bar(x, y + 8, "MP", player.mana, player.max_mana, MANA)
        return y

    def draw_stat_bar(self, x: int, y: int, label: str, value: int, maximum: int, color: tuple[int, int, int]) -> int:
        self.draw_text(f"{label} {value}/{maximum}", x, y, self.small_font, TEXT)
        bar_x = x + 86
        bar_y = y + 3
        width = 220
        height = 12
        pygame.draw.rect(self.screen, (48, 50, 58), (bar_x, bar_y, width, height), border_radius=3)
        fill_width = int(width * (value / max(1, maximum)))
        pygame.draw.rect(self.screen, color, (bar_x, bar_y, fill_width, height), border_radius=3)
        return y + 22

    def draw_statuses(self, x: int, y: int, player: Entity) -> int:
        statuses = player.statuses
        if not statuses:
            return y
        STATUS_COLORS = {
            "burning": (232, 96, 70),
            "poisoned": (130, 200, 80),
            "bleeding": (220, 70, 70),
            "frozen": (156, 210, 224),
            "stunned": (220, 220, 100),
            "rooted": (100, 180, 100),
            "webbed": (200, 200, 150),
            "berserk": (220, 80, 80),
            "empowered": (255, 180, 50),
            "warded": (120, 180, 255),
            "invisible": (170, 170, 200),
            "regenerating": (100, 220, 150),
            "hasted": (220, 220, 255),
        }
        y = self.draw_text("Statuses", x, y, self.small_font, MUTED)
        parts = []
        for key, val in sorted(statuses.items()):
            display = player.status_display.get(key, key).replace("_", " ")
            dur = "" if val == "permanent" else f":{val}"
            parts.append((display + dur, STATUS_COLORS.get(key, TEXT)))
        line_parts: list[tuple[str, tuple[int, int, int]]] = []
        line_width = 0
        max_width = PANEL_WIDTH - 50
        for label, color in parts:
            w = self.small_font.size(label + "  ")[0]
            if line_width + w > max_width and line_parts:
                y = self.draw_colored_chips(x, y, line_parts)
                line_parts = []
                line_width = 0
            line_parts.append((label, color))
            line_width += w
        if line_parts:
            y = self.draw_colored_chips(x, y, line_parts)
        return y

    def draw_colored_chips(self, x: int, y: int, parts: list[tuple[str, tuple[int, int, int]]]) -> int:
        cx = x
        for label, color in parts:
            surface = self.small_font.render(label, True, color)
            self.screen.blit(surface, (cx, y))
            cx += surface.get_width() + 10
        return y + self.small_font.get_linesize() + 2

    def draw_visible_enemies(self, x: int, y: int) -> int:
        engine = self.engine
        player = engine.state.player
        all_enemies = engine.living_enemies()
        visible = [e for e in all_enemies if engine.is_visible(e.x, e.y)]
        hidden = len(all_enemies) - len(visible)
        if not all_enemies:
            return y
        y = self.draw_text(
            f"Enemies  {len(visible)} visible" + (f"  {hidden} unseen" if hidden else ""),
            x, y, self.small_font, DANGER if visible else MUTED
        )
        for enemy in sorted(visible, key=lambda e: engine.distance(player, e))[:4]:
            hp_frac = enemy.hp / max(1, enemy.max_hp)
            bar_color = DANGER if hp_frac < 0.4 else GOLD if hp_frac < 0.7 else (160, 200, 140)
            status_chips = " ".join(
                enemy.status_display.get(k, k) for k in sorted(enemy.statuses)[:2]
            )
            suffix = f"  {status_chips}" if status_chips else ""
            label = f"  {enemy.name} {enemy.hp}/{enemy.max_hp}{suffix}"
            y = self.draw_text(label, x, y, self.small_font, bar_color)
        if len(visible) > 4:
            y = self.draw_text(f"  …+{len(visible)-4} more", x, y, self.small_font, MUTED)
        return y

    def draw_floor_items(self, x: int, y: int) -> int:
        engine = self.engine
        player = engine.state.player
        visible_items = [
            e for e in engine.state.entities.values()
            if e.kind == "item" and engine.is_visible(e.x, e.y)
        ]
        if not visible_items:
            return y
        at_feet = [e for e in visible_items if e.x == player.x and e.y == player.y]
        nearby = [e for e in visible_items if e not in at_feet][:4]
        y = self.draw_text("Floor", x, y, self.small_font, GOLD)
        if at_feet:
            names = ", ".join(e.name for e in at_feet[:3])
            y = self.draw_text(f"[here] {names}", x, y, self.small_font, ACCENT)
        for item in nearby:
            dx = item.x - player.x
            dy = item.y - player.y
            dist = int((dx * dx + dy * dy) ** 0.5)
            y = self.draw_text(f"[{dist}] {item.name}", x, y, self.small_font, TEXT)
        return y

    def draw_inventory(self, x: int, y: int) -> int:
        state = self.engine.state
        items = ", ".join(f"{name} x{amount}" for name, amount in state.inventory.items()) or "empty"
        y = self.draw_text("Inventory", x, y, self.small_font, GOLD)
        for line in wrap_text(items, 42):
            y = self.draw_text(line, x, y, self.small_font, TEXT)
        return y

    def draw_curses(self, x: int, y: int) -> int:
        curses = list(self.engine.state.curses.values())
        y = self.draw_text("Curses", x, y, self.small_font, DANGER if curses else MUTED)
        if not curses:
            return self.draw_text("none", x, y, self.small_font, MUTED)
        for curse in curses[-3:]:
            text = f"{curse.name} x{curse.stacks}"
            y = self.draw_text(text, x, y, self.small_font, TEXT)
        return y

    def draw_log(self, x: int, y: int, height: int) -> None:
        self.log_line_rects = []
        self.log_area = pygame.Rect(x, y, PANEL_WIDTH - 40, height)
        pygame.draw.line(self.screen, PANEL_EDGE, (x, y - 8), (WINDOW_WIDTH - 20, y - 8), 1)
        line_y = y
        lines: list[tuple[str, bool]] = []
        line_height = self.small_font.get_linesize() + 2
        max_lines = max(1, height // line_height)
        for message in self.engine.state.messages[-40:]:
            is_prompt = message.startswith(">") or message.startswith("*>")
            lines.extend((line, is_prompt) for line in wrap_text(message, 45))
        visible_lines = lines[-max_lines:]
        selected_indexes = self.selected_log_indexes(len(visible_lines))
        for index, (line, is_prompt) in enumerate(visible_lines):
            color = MUTED if is_prompt else TEXT
            rect = pygame.Rect(x - 4, line_y - 1, PANEL_WIDTH - 32, line_height)
            if index in selected_indexes:
                pygame.draw.rect(self.screen, SELECTED, rect, border_radius=3)
            line_y = self.draw_text(line, x, line_y, self.small_font, color)
            self.log_line_rects.append((rect, line))
            if line_y > y + height:
                break

    def selected_log_indexes(self, visible_line_count: int) -> set[int]:
        if self.log_selection_anchor is None or self.log_selection_focus is None:
            return set()
        if not self.log_line_rects and visible_line_count == 0:
            return set()
        start = min(self.log_selection_anchor, self.log_selection_focus)
        end = max(self.log_selection_anchor, self.log_selection_focus)
        return {index for index in range(max(0, start), min(visible_line_count - 1, end) + 1)}

    def spell_box_height(self) -> int:
        line_count = len(wrap_text(self.input_text or " ", 42))
        visible_lines = min(max(2, line_count), 6)
        return 18 + visible_lines * 18

    def draw_spell_box(self, x: int, y: int, height: int) -> None:
        width = PANEL_WIDTH - 40
        pygame.draw.line(self.screen, PANEL_EDGE, (x, y - 14), (WINDOW_WIDTH - 20, y - 14), 1)
        label_color = ACCENT if self.input_active else MUTED
        self.draw_text("Wild Spell", x, y - 26, self.small_font, label_color)
        rect = pygame.Rect(x, y, width, height)
        self.spell_box_rect = rect
        pygame.draw.rect(self.screen, (17, 19, 24), rect, border_radius=6)
        pygame.draw.rect(self.screen, ACCENT if self.input_active else PANEL_EDGE, rect, width=1, border_radius=6)
        shown = self.input_text
        if self.input_active and pygame.time.get_ticks() % 1000 < 500:
            shown += "_"
        lines = wrap_text(shown or " ", 42)
        max_visible_lines = max(1, (height - 18) // 18)
        visible_lines = lines[-max_visible_lines:]
        if len(lines) > max_visible_lines and visible_lines:
            visible_lines[0] = "..." + visible_lines[0][-39:]
        for index, line in enumerate(visible_lines):
            self.draw_text(line, x + 10, y + 9 + index * 18, self.ui_font, TEXT)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        color: tuple[int, int, int],
    ) -> int:
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))
        return y + surface.get_height() + 2


def blend_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
    )


def wrap_text(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    for raw_line in text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=width, replace_whitespace=False) or [""]
        lines.extend(wrapped)
    return lines


def dim_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return (max(20, color[0] // 3), max(20, color[1] // 3), max(24, color[2] // 3))


def run_game() -> None:
    GameUI().run()
