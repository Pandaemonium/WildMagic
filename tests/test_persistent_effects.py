"""Engine + routing tests for the persistent-effect substrate and the two cards built on
it: create_persistent_effect, the sympathetic_link relationship, and the persistent_effect
creature-bound ward. Item-bound enchantments are intentionally out of scope (no item-
instance state yet), so nothing here touches inventory or equipment."""

from __future__ import annotations

from wildmagic import capabilities as cap
from wildmagic.engine import GameEngine
from wildmagic.normalize import normalize_trigger_name
from wildmagic.spell_contract import SUPPORTED_EFFECTS, validate_resolution


def _engine_with_enemy(hp: int = 30, attack: int = 4):
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    enemy = engine.spawn_actor(
        "brute", "B", player.x + 1, player.y, hp, attack, 0, "enemy", None
    )
    return engine, player, enemy


# --- sympathetic_link -------------------------------------------------------------------


def test_sympathetic_link_echoes_damage_to_the_sink() -> None:
    """Whatever wounds the source wounds the sink: the actual damage the player takes is
    echoed onto the linked enemy."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": "player",
            "sink": enemy.id,
            "duration": 8,
        }
    )
    enemy_before = enemy.hp
    player_before = player.hp
    engine.damage_entity(player, 5, "arcane")
    player_loss = player_before - player.hp
    enemy_loss = enemy_before - enemy.hp
    assert player_loss > 0
    assert enemy_loss == player_loss  # ratio 1.0 echo


def test_sympathetic_link_ratio_scales_the_echo() -> None:
    """ratio 0.5 -> the sink takes half the source's wound (rounded)."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": "player",
            "sink": enemy.id,
            "ratio": 0.5,
            "duration": 8,
        }
    )
    enemy_before = enemy.hp
    player_before = player.hp
    engine.damage_entity(player, 6, "arcane")
    player_loss = player_before - player.hp
    enemy_loss = enemy_before - enemy.hp
    assert enemy_loss == max(1, round(player_loss * 0.5))


def test_mutual_link_terminates_and_does_not_double_count() -> None:
    """A mutual A<->B link must not recurse forever (the trigger store is emptied during a
    fire, so the echo's own damage cannot re-fire the link) and must not double-apply: one
    hit on A lands once on A and once on B."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": "player",
            "sink": enemy.id,
            "mutual": True,
            "duration": 8,
        }
    )
    enemy_before = enemy.hp
    player_before = player.hp
    engine.damage_entity(player, 4, "arcane")  # returns -> no stack overflow
    assert (
        player_before - player.hp == 4
    )  # only the original hit, no echo back onto self
    assert enemy_before - enemy.hp == 4  # the single forward echo


def test_sympathetic_link_refuses_to_bind_a_thing_to_itself() -> None:
    engine, player, enemy = _engine_with_enemy()
    messages = engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": "player",
            "sink": "player",
        }
    )
    assert messages and "itself" in messages[0].lower()
    assert engine.state.triggers == []


def test_link_unravels_when_an_end_dies() -> None:
    """The link ends when either bound creature dies -- the anchor-lifecycle prune in
    _tick_triggers drops it (and says so)."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": "player",
            "sink": enemy.id,
            "duration": 8,
        }
    )
    assert len(engine.state.triggers) == 1
    enemy.hp = 0  # the sink dies
    engine._tick_triggers()
    assert engine.state.triggers == []


# --- persistent_effect (creature-bound ward) --------------------------------------------


def test_persistent_effect_afflicts_whoever_strikes_the_anchor() -> None:
    """A hex bound to the enemy: anyone who strikes it is poisoned. Firing the anchor's
    on_damaged hook applies the nested status to the attacker (trigger_source)."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": enemy.id,
            "hook": "on_damaged",
            "name": "blistering hex",
            "duration": 6,
            "effects": [
                {
                    "type": "add_status",
                    "target": "trigger_source",
                    "status": "poisoned",
                    "duration": 3,
                }
            ],
        }
    )
    assert "poisoned" not in player.statuses
    # The player strikes the hexed enemy; the hex answers onto the player.
    engine.attack(player, enemy)
    assert player.statuses.get("poisoned") == 3


def test_persistent_effect_with_no_effects_fizzles_without_registering() -> None:
    engine, player, enemy = _engine_with_enemy()
    messages = engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": enemy.id,
            "effects": [],
        }
    )
    assert messages and isinstance(messages[0], str)
    assert engine.state.triggers == []


# --- contract ---------------------------------------------------------------------------


def test_contract_registers_the_effect() -> None:
    assert "create_persistent_effect" in SUPPORTED_EFFECTS


def test_validation_requires_effects_for_non_link_persistent() -> None:
    err = validate_resolution(
        {
            "accepted": True,
            "severity": "minor",
            "outcome_text": "x",
            "effects": [
                {"type": "create_persistent_effect", "kind": "persistent_effect"}
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )
    assert err is not None and "create_persistent_effect" in err


def test_validation_exempts_sympathetic_link_from_effects_requirement() -> None:
    err = validate_resolution(
        {
            "accepted": True,
            "severity": "minor",
            "outcome_text": "x",
            "effects": [
                {
                    "type": "create_persistent_effect",
                    "kind": "sympathetic_link",
                    "source": "player",
                    "sink": "nearest_enemy",
                }
            ],
            "costs": [],
            "rejected_reason": None,
        }
    )
    assert err is None


# --- routing ----------------------------------------------------------------------------


def test_sympathetic_phrasings_select_sympathetic_link() -> None:
    for text in (
        "whatever wounds me wounds the brute",
        "bind the goblin's pain to the ogre",
        "tie their heartbeats together",
        "make the doll suffer what he suffers",
    ):
        assert "sympathetic_link" in {c.name for c in cap.select_cards(text)}, text


def test_persistent_ward_phrasing_selects_persistent_effect() -> None:
    selected = {
        c.name for c in cap.select_cards("hex the ogre so anyone who strikes it rots")
    }
    assert "persistent_effect" in selected


def test_new_cards_unlock_the_persistent_effect() -> None:
    for name in ("sympathetic_link", "persistent_effect"):
        card = next(c for c in cap.CAPABILITY_CARDS if c.name == name)
        assert card.effect_types == ("create_persistent_effect",)
        assert card.integrated is True


def test_plain_fireball_still_loads_no_persistent_card() -> None:
    selected = {
        c.name for c in cap.select_cards("hurl a roaring fireball at the goblin")
    }
    assert "sympathetic_link" not in selected
    assert "persistent_effect" not in selected


# --- universal "on hit" hook (works on any entity, not just the player) -----------------


def test_generic_hit_words_normalize_to_universal_hook() -> None:
    """'on hit / struck / took damage' with no named subject is the universal on_damaged,
    which fires for any entity; only explicitly-player phrasings stay player-scoped."""
    for word in ("on_hit", "when hit", "on_struck", "on_take_damage", "on_wounded"):
        assert normalize_trigger_name(word) == "on_damaged", word
    assert normalize_trigger_name("on_player_hit") == "on_player_hit"
    assert normalize_trigger_name("when_i_am_hit") == "on_player_hit"


def test_persistent_ward_on_an_ally_afflicts_its_attacker() -> None:
    """An ally has no faction-specific damage hook -- the ward must still fire via the
    universal on_hit. An enemy striking the warded ally is burned."""
    engine, player, enemy = _engine_with_enemy()
    ally = engine.spawn_actor(
        "hound", "h", player.x, player.y + 1, 20, 3, 0, "ally", None
    )
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": ally.id,
            "hook": "on_hit",
            "name": "thornmail ward",
            "duration": 6,
            "effects": [
                {
                    "type": "add_status",
                    "target": "trigger_source",
                    "status": "burning",
                    "duration": 3,
                }
            ],
        }
    )
    engine.attack(enemy, ally)  # the enemy strikes the warded ally
    assert ally.hp > 0
    assert enemy.statuses.get("burning") == 3


def test_sympathetic_link_works_between_two_enemies() -> None:
    """Enemy-vs-enemy: a link bound to one enemy echoes its wounds onto another, no player
    involvement -- the universal on_damaged hook makes this work."""
    engine, player, enemy_a = _engine_with_enemy()
    enemy_b = engine.spawn_actor(
        "ogre", "O", player.x + 2, player.y, 30, 5, 0, "enemy", None
    )
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "sympathetic_link",
            "source": enemy_a.id,
            "sink": enemy_b.id,
            "duration": 8,
        }
    )
    b_before = enemy_b.hp
    engine.damage_entity(enemy_a, 5, "arcane")
    assert b_before - enemy_b.hp == 5


def test_free_floating_hit_ward_defaults_to_the_caster() -> None:
    """A free-floating 'when I'm hit, lash back' ward with no named subject stays scoped to
    the player: it fires when the player is struck, NOT when an ally strikes a foe."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_trigger",
            "trigger": "on_hit",  # no explicit target
            "effects": [
                {
                    "type": "damage",
                    "target": "trigger_source",
                    "amount": 3,
                    "damage_type": "fire",
                }
            ],
        }
    )
    assert engine.state.triggers[0]["target"] == "player"  # defaulted to the caster
    # An unrelated creature being hit must NOT trip the player's ward.
    bystander = engine.spawn_actor(
        "rat", "r", player.x, player.y + 1, 10, 1, 0, "enemy", None
    )
    enemy_before = enemy.hp
    engine.damage_entity(bystander, 4, "arcane", source=enemy)
    assert enemy.hp == enemy_before  # ward did not retaliate for the bystander
    # The player being hit DOES trip it -- the attacker takes the lash.
    engine.damage_entity(player, 4, "arcane", source=enemy)
    assert enemy_before - enemy.hp == 3


# --- attacker side: an effect that rides the blows the anchor lands ----------------------


def test_attacker_words_normalize_to_deal_damage() -> None:
    for word in (
        "on_strike",
        "on_attack",
        "when_i_strike",
        "on_deal_damage",
        "on_melee",
    ):
        assert normalize_trigger_name(word) == "on_deal_damage", word


def test_attacker_rider_bleeds_whatever_the_anchor_strikes() -> None:
    """'make my blade bleed whatever I strike': anchored on the player, fires when the
    player lands a blow, and afflicts the victim (trigger_target)."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": "player",
            "hook": "on_strike",
            "name": "envenomed blows",
            "duration": 6,
            "effects": [
                {
                    "type": "add_status",
                    "target": "trigger_target",
                    "status": "bleeding",
                    "duration": 3,
                }
            ],
        }
    )
    # The trigger is source-matched (attacker side), keyed to the player.
    assert engine.state.triggers[0]["match"] == "source"
    assert engine.state.triggers[0]["target"] == player.id
    engine.attack(player, enemy)  # the player lands a blow
    assert enemy.statuses.get("bleeding") == 3


def test_attacker_rider_only_fires_for_its_anchor() -> None:
    """The rider rides the ANCHOR's blows, not blows landed on the anchor: when the enemy
    strikes the player, the player's own attack-rider must stay silent."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": "player",
            "hook": "on_strike",
            "duration": 6,
            "effects": [
                {
                    "type": "add_status",
                    "target": "trigger_target",
                    "status": "bleeding",
                    "duration": 3,
                }
            ],
        }
    )
    engine.attack(enemy, player)  # the enemy strikes the player
    assert "bleeding" not in player.statuses  # the player's attack-rider did not fire


def test_attacker_rider_ignores_sourceless_damage() -> None:
    """Environmental damage (a hazard tile, no attacker) has no source, so a source-matched
    rider never fires off it -- and nothing crashes."""
    engine, player, enemy = _engine_with_enemy()
    engine._apply_effect(
        {
            "type": "create_persistent_effect",
            "kind": "persistent_effect",
            "anchor": "player",
            "hook": "on_strike",
            "duration": 6,
            "effects": [
                {
                    "type": "add_status",
                    "target": "trigger_target",
                    "status": "bleeding",
                    "duration": 3,
                }
            ],
        }
    )
    engine.damage_entity(enemy, 3, "fire")  # no source -> sourceless
    assert "bleeding" not in enemy.statuses
