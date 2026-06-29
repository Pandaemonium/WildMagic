from __future__ import annotations

import random

from wildmagic.actions import GameSession, describe_reagents, inventory_item_summary
from wildmagic.engine import GameEngine
from wildmagic.item_identification import (
    identification_fee,
    identified_item_value,
    item_identification_context,
    normalize_item_identification,
    validate_item_identification,
)
from wildmagic.item_ability_cards import select_item_ability_cards
from wildmagic.item_catalog import item_definition, item_value
from wildmagic.item_generation import generate_curio
from wildmagic.item_palettes import palette_colors, palette_label, palette_prompt_cards
from wildmagic.normalize import normalize_id
from wildmagic.persistence import engine_from_snapshot, engine_to_snapshot
from wildmagic.state_view import equipment_inventory_view, spell_context_view


def _resolution(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "accepted": True,
        "severity": "minor",
        "outcome_text": "The spell answers.",
        "effects": [{"type": "message", "message": "A harmless light flickers."}],
        "costs": [],
        "rejected_reason": None,
    }
    data.update(overrides)
    return data


def test_item_catalog_gives_gold_and_semantic_curios_reagent_value() -> None:
    assert item_value("gold") == 1
    grave_salt = item_definition("grave salt")
    assert grave_salt.value > item_value("gold")
    assert "binding" in grave_salt.tags

    crystal_ball = item_definition("crystal ball")
    assert crystal_ball.value > grave_salt.value
    assert "divination" in crystal_ball.tags


def test_generated_curio_lore_drives_reagent_card_and_cost_value() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    curio = generate_curio(
        random.Random(3),
        themes=["empire", "lore"],
        source="test",
    )
    engine.state.inventory[curio.name] = 1
    engine.set_item_lore(
        curio.name,
        curio.name,
        curio.description,
        source="generated",
        metadata=curio.lore_metadata(),
    )

    context = spell_context_view(engine, f"burn the {curio.name}")
    card = next(card for card in context["reagents"] if card["name"] == curio.name)

    assert card["value"] == curio.value
    assert card["total_value"] == curio.value
    assert card["material"] == curio.material
    assert set(curio.tags).issubset(set(card["tags"]))
    assert card["description"] == curio.description

    outcome = engine.apply_wild_magic_resolution(
        _resolution(costs=[{"type": "item", "item": curio.name, "amount": 1}])
    )

    assert outcome.technical_failure is False
    assert curio.name not in engine.state.inventory
    assert any(
        f"Cost: {curio.name} (value {curio.value})." in message
        for message in outcome.messages
    )


def test_reagent_description_surfaces_for_generated_curios() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    curio = generate_curio(random.Random(8), themes=["secret"], source="test")
    engine.state.inventory[curio.name] = 1
    engine.set_item_lore(
        curio.name,
        curio.name,
        curio.description,
        source="generated",
        metadata=curio.lore_metadata(),
    )

    lines = describe_reagents(engine)

    assert any(curio.name in line for line in lines)
    assert any(curio.description[:40] in line for line in lines)


def test_pickup_preserves_generated_curio_metadata_as_item_lore() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    curio = generate_curio(random.Random(5), themes=["death"], source="test_loot")
    item = engine.spawn_item(
        curio.name,
        "?",
        player.x,
        player.y,
        item_type=curio.name,
        material=curio.material,
        tags=set(curio.tags),
    )
    item.description = curio.description
    item.details["item_metadata"] = curio.lore_metadata()

    engine.pick_up_items_at_player()

    lore = engine.state.item_lore[normalize_id(curio.name)]
    assert lore["description"] == curio.description
    assert lore["value"] == curio.value
    assert lore["material"] == curio.material
    assert set(curio.tags).issubset(set(lore["tags"]))


def test_conjured_named_item_keeps_name_when_picked_up() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")

    outcome = engine.apply_wild_magic_resolution(
        _resolution(
            effects=[
                {
                    "type": "conjure_item",
                    "template": "generic_object",
                    "name": "singing compass",
                    "target": "player",
                    "placement": "near_player",
                    "tags": ["music", "direction"],
                }
            ]
        )
    )
    assert outcome.technical_failure is False

    item = next(
        entity
        for entity in engine.state.entities.values()
        if entity.kind == "item" and entity.name == "singing compass"
    )
    player = engine.state.player
    player.x = item.x
    player.y = item.y

    assert engine.pick_up_items_at_player() is True
    assert engine.state.inventory["singing compass"] == 1
    assert "object" not in engine.state.inventory
    assert engine.protect_item("singing compass") is True
    assert engine.is_item_protected("singing compass")


def test_spell_context_includes_unprotected_reagent_cards_and_gold() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")

    context = spell_context_view(engine, "bind the goblin with grave salt")
    reagents = {card["name"]: card for card in context["reagents"]}

    assert reagents["gold"]["value"] == 1
    assert reagents["grave salt"]["value"] == item_value("grave salt")
    assert reagents["grave salt"]["total_value"] == (
        item_value("grave salt") * engine.state.inventory["grave salt"]
    )
    assert "binding" in reagents["grave salt"]["tags"]
    assert context["protected_inventory"] == []


def test_protect_hides_stack_from_reagents_until_unprotected() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")

    assert engine.protect_item("grave salt") is True
    protected_context = spell_context_view(engine, "burn grave salt")

    assert "grave salt" not in {card["name"] for card in protected_context["reagents"]}
    protected = {
        card["name"]: card for card in protected_context["protected_inventory"]
    }
    assert protected["grave salt"]["protected"] is True
    assert protected["grave salt"]["spendable"] is False

    assert engine.unprotect_item("grave salt") is True
    unprotected_context = spell_context_view(engine, "burn grave salt")
    assert "grave salt" in {card["name"] for card in unprotected_context["reagents"]}
    assert unprotected_context["protected_inventory"] == []


def test_reagent_commands_are_free_and_shared_through_session() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        turn_before = session.engine.state.turn

        protect = session.execute_command("protect grave salt")
        assert protect.success is True
        assert session.engine.state.turn == turn_before
        assert session.engine.is_item_protected("grave salt")

        reagents = session.execute_command("reagents")
        assert reagents.success is True
        assert any(
            "Protected from wild magic" in message for message in reagents.messages
        )

        unprotect = session.execute_command("unprotect grave salt")
        assert unprotect.success is True
        assert session.engine.state.turn == turn_before
        assert not session.engine.is_item_protected("grave salt")
    finally:
        session.close()


def test_empty_pickup_reports_no_item_and_costs_no_turn() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        turn_before = session.engine.state.turn

        result = session.execute_command("pickup")

        assert result.success is False
        assert result.consumed_turn is False
        assert session.engine.state.turn == turn_before
        assert result.messages == ["There is nothing here to pick up."]
    finally:
        session.close()


def test_item_cost_fuzzy_matches_inventory_and_reports_value() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    before = engine.state.inventory["grave salt"]

    outcome = engine.apply_wild_magic_resolution(
        _resolution(costs=[{"type": "item", "item": "grave_salt", "amount": 1}])
    )

    assert outcome.technical_failure is False
    assert engine.state.inventory["grave salt"] == before - 1
    assert any("Cost: grave salt (value 4)." in message for message in outcome.messages)


def test_item_cost_accepts_name_alias() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    before = engine.state.inventory["grave salt"]

    outcome = engine.apply_wild_magic_resolution(
        _resolution(costs=[{"type": "item", "name": "grave salt", "amount": 1}])
    )

    assert outcome.technical_failure is False
    assert engine.state.inventory["grave salt"] == before - 1
    assert any("Cost: grave salt (value 4)." in message for message in outcome.messages)


def test_protected_item_cost_fails_before_effects_apply() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    before = engine.state.inventory["grave salt"]
    turn_before = engine.state.turn
    assert engine.protect_item("grave salt") is True

    outcome = engine.apply_wild_magic_resolution(
        _resolution(
            effects=[
                {
                    "type": "add_status",
                    "target": "player",
                    "status": "warded",
                    "duration": 5,
                }
            ],
            costs=[{"type": "item", "item": "grave salt", "amount": 1}],
        )
    )

    assert outcome.technical_failure is True
    assert outcome.consumed_turn is False
    assert engine.state.inventory["grave salt"] == before
    assert engine.state.turn == turn_before
    assert engine.is_item_protected("grave salt")
    assert "warded" not in engine.state.player.statuses
    assert any("is protected" in message for message in outcome.messages)


def test_unavailable_item_cost_fails_before_effects_apply() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    turn_before = engine.state.turn

    outcome = engine.apply_wild_magic_resolution(
        _resolution(
            effects=[
                {
                    "type": "add_status",
                    "target": "player",
                    "status": "warded",
                    "duration": 5,
                }
            ],
            costs=[{"type": "item", "item": "crystal ball", "amount": 1}],
        )
    )

    assert outcome.technical_failure is True
    assert outcome.consumed_turn is False
    assert engine.state.turn == turn_before
    assert "warded" not in engine.state.player.statuses
    assert any("is not carried" in message for message in outcome.messages)


def test_protected_inventory_round_trips_in_engine_snapshot() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    assert engine.protect_item("grave salt") is True

    restored = engine_from_snapshot(engine_to_snapshot(engine), provider_name="mock")

    assert (
        restored.state.inventory["grave salt"] == engine.state.inventory["grave salt"]
    )
    assert restored.is_item_protected("grave salt")


def test_mana_crystal_is_not_consumed_when_mana_is_full() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    before = engine.state.inventory["mana crystal"]
    turn_before = engine.state.turn

    assert engine.use_item("mana crystal") is False

    assert engine.state.inventory["mana crystal"] == before
    assert engine.state.turn == turn_before
    assert "crystal stays whole" in engine.state.messages[-1]


def test_mana_crystal_consumes_when_it_restores_mana() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.mana = max(0, player.mana - 4)
    before = engine.state.inventory["mana crystal"]
    turn_before = engine.state.turn

    assert engine.use_item("mana crystal") is True

    assert engine.state.inventory["mana crystal"] == before - 1
    assert player.mana == player.max_mana
    assert engine.state.turn == turn_before + 1


def test_blood_moss_is_not_consumed_when_unhurt() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    before = engine.state.inventory["blood moss"]
    turn_before = engine.state.turn

    assert engine.use_item("blood moss") is False

    assert engine.state.inventory["blood moss"] == before
    assert engine.state.turn == turn_before
    assert "moss can wait" in engine.state.messages[-1]


def test_blood_moss_consumes_when_it_heals() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    player = engine.state.player
    player.hp = max(1, player.hp - 3)
    before = engine.state.inventory["blood moss"]
    turn_before = engine.state.turn

    assert engine.use_item("blood moss") is True

    assert engine.state.inventory["blood moss"] == before - 1
    assert player.hp == player.max_hp
    assert engine.state.turn == turn_before + 1


def _spawn_identifier(session: GameSession) -> None:
    player = session.engine.state.player
    session.engine.spawn_npc(
        "Marta Glass",
        "m",
        player.x + 1,
        player.y,
        role="merchant",
        backstory="A market appraiser who knows which objects are awake.",
        wares={"gold": 20},
    )
    session.engine.update_fov()


def test_identify_command_costs_gold_turn_and_splits_stack() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        _spawn_identifier(session)
        session.engine.state.inventory["plain spoon"] = 2
        before_gold = session.engine.state.inventory["gold"]
        turn_before = session.engine.state.turn
        base_value = item_value("plain spoon")
        fee = identification_fee(base_value, "merchant")
        value_after = identified_item_value(base_value, fee)

        result = session.execute_command("identify plain spoon")

        assert result.success is True
        assert result.consumed_turn is True
        assert session.engine.state.turn == turn_before + 1
        assert session.engine.state.inventory["gold"] == before_gold - fee
        assert session.engine.state.inventory["plain spoon"] == 1
        identified_items = [
            name
            for name in session.engine.state.inventory
            if normalize_id("plain spoon") in normalize_id(name)
            and name != "plain spoon"
        ]
        assert identified_items
        lore = session.engine.state.item_lore[normalize_id(identified_items[0])]
        assert lore["identified"] is True
        assert lore["descriptor"]
        assert lore["palette_id"]
        assert lore["ability_summary"]
        assert lore["value"] == value_after
        assert lore["identification_fee"] == fee
        assert lore["base_item"] == "plain spoon"
        assert result.item_identification is not None
        assert result.item_identification["technical_failure"] is False
        messages = "\n".join(str(message) for message in session.engine.state.messages)
        assert "Ability:" in messages
        assert "coaxed into a usable charm" in messages
    finally:
        session.close()


def test_identified_item_can_be_used_without_being_consumed_until_charges_run_out() -> (
    None
):
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        _spawn_identifier(session)
        session.engine.state.inventory["moon glass"] = 1
        session.engine.state.player.mana = max(0, session.engine.state.player.mana - 5)

        assert session.execute_command("identify moon glass").success is True
        identified = next(
            name
            for name in session.engine.state.inventory
            if normalize_id("moon glass") in normalize_id(name)
        )
        before_qty = session.engine.state.inventory[identified]
        before_turn = session.engine.state.turn

        result = session.execute_command(f"use {identified}")

        assert result.success is True
        assert session.engine.state.turn == before_turn + 1
        assert session.engine.state.inventory[identified] == before_qty
        lore = session.engine.state.item_lore[normalize_id(identified)]
        assert lore["use_spec"]["charges"] >= 0
    finally:
        session.close()


def test_identified_item_can_be_addressed_by_original_name_after_rename() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.inventory["moon glass"] = 1
    engine.state.player.mana = max(0, engine.state.player.mana - 4)

    identified = engine.identify_inventory_item(
        "moon glass",
        {
            "descriptor": "moonlit",
            "palette_id": "moon_opal",
            "display_name": "moon glass shard",
            "description": "A singing sliver of moonlit glass.",
            "ability_summary": "Use it to restore mana.",
            "tags": ["moon", "glass"],
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "restore_mana", "amount": 4}],
                "message": "The {item} rings softly. You recover {amount} mana.",
                "failure": "Your mana is already full.",
                "consume_on_use": False,
                "charges": 3,
            },
        },
        npc_name="Marta Glass",
        fee=5,
        value_after=22,
        base_value=18,
    )

    assert identified == "moonlit moon glass shard"
    assert engine.find_inventory_item("moon glass") == "moonlit moon glass shard"
    assert (
        engine.find_inventory_item("identified moon glass")
        == "moonlit moon glass shard"
    )
    assert engine.use_item("identified moon glass") is True
    assert engine.state.inventory["moonlit moon glass shard"] == 1


def test_identified_item_with_same_display_name_does_not_stack_with_raw_item() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.inventory["bone seal"] = 1

    identified = engine.identify_inventory_item(
        "bone seal",
        {
            "descriptor": "ivory",
            "palette_id": "salt_ivory",
            "display_name": "bone seal",
            "description": "An official-looking bone charm.",
            "ability_summary": "Equip it in your charm slot for +1 defense.",
            "tags": ["bone", "seal"],
            "ability_kind": "slot_passive",
            "equipment_slot": "charm",
            "equipment_spec": {"defense": 1},
            "use_spec": {
                "effects": [{"kind": "status", "status": "warded", "duration": 5}],
                "message": "The {item} clicks shut around you. You are warded.",
                "failure": "The item refuses to wake.",
                "consume_on_use": False,
                "charges": 2,
            },
        },
        npc_name="Marta Glass",
        fee=5,
        value_after=29,
        base_value=25,
    )

    assert identified == "ivory bone seal"
    assert engine.find_inventory_item("identified bone seal") == identified
    engine.add_inventory_item(engine.state.inventory, "bone seal", 1)

    assert engine.state.inventory["ivory bone seal"] == 1
    assert engine.state.inventory["bone seal"] == 1


def test_identified_slot_passive_can_be_equipped_and_grants_dynamic_bonus() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        _spawn_identifier(session)
        session.engine.state.inventory["bone seal"] = 1

        assert session.execute_command("identify bone seal").success is True
        identified = next(
            name
            for name in session.engine.state.inventory
            if normalize_id("bone seal") in normalize_id(name)
        )
        lore = session.engine.state.item_lore[normalize_id(identified)]
        assert lore.get("ability_kind") == "slot_passive"
        before_defense = session.engine.effective_defense(session.engine.state.player)

        result = session.execute_command(f"equip {identified}")

        assert result.success is True
        assert session.engine.state.player.equipment.get("charm") == identified
        assert (
            session.engine.effective_defense(session.engine.state.player)
            > before_defense
        )
    finally:
        session.close()


def test_identification_replay_payload_reapplies_without_provider_call() -> None:
    session = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        _spawn_identifier(session)
        session.engine.state.inventory["singing pebble"] = 1

        result = session.execute_command("identify singing pebble")
        assert result.success is True
        assert result.item_identification is not None
        replay_payload = dict(result.item_identification)
    finally:
        session.close()

    replayed = GameSession(seed=7, scenario="test_chamber", provider_name="mock")
    try:
        _spawn_identifier(replayed)
        replayed.engine.state.inventory["singing pebble"] = 1
        before_turn = replayed.engine.state.turn

        result = replayed.execute_command(
            "identify singing pebble",
            replay_item_identification=replay_payload,
        )

        assert result.success is True
        assert replayed.engine.state.turn == before_turn + 1
        assert result.item_identification == replay_payload
    finally:
        replayed.close()


def test_item_identification_normalization_adds_identity_fields() -> None:
    context = {
        "item": {
            "name": "mana crystal",
            "value": 8,
            "material": "crystal",
            "tags": ["mana", "crystal"],
        },
        "identification": {"value_after": 12},
    }
    normalized = normalize_item_identification(
        {
            "identified": True,
            "display_name": "mana crystal",
            "description": "A humming crystal full of clear spell-light.",
            "tags": ["mana"],
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "restore_mana", "amount": 4}],
                "message": "The {item} sings.",
                "failure": "It stays quiet.",
                "consume_on_use": False,
                "charges": 3,
            },
        },
        context,
    )

    assert validate_item_identification(normalized) is None
    assert normalized["descriptor"]
    assert normalized["palette_id"] == "moon_opal"
    assert normalized["display_name"] == f"{normalized['descriptor']} mana crystal"
    assert normalized["ability_summary"]


def test_item_identification_compact_card_id_expands_to_use_spec() -> None:
    item_card = {
        "name": "debtor coin",
        "value": 8,
        "material": "gold",
        "tags": ["coin", "debt", "law", "curse"],
    }
    context = item_identification_context(
        item_card=item_card,
        npc_card={"name": "Marta Glass", "role": "merchant"},
        fee=5,
        value_after=12,
    )

    normalized = normalize_item_identification(
        {
            "identified": True,
            "descriptor": "violet",
            "palette_id": "violet_ink",
            "display_name": "debtor coin",
            "description": "The coin ticks like an unpaid clock.",
            "ability_summary": "Use it to curse the nearest enemy with bad luck.",
            "tags": ["coin", "debt"],
            "ability_card_id": "debt_binding",
            "effect_overrides": {
                "status": "cursed",
                "duration": 6,
                "message": "The {item} names {target}. They are {status}.",
                "failure": "No enemy is close enough to owe you.",
                "charges": 2,
            },
        },
        context,
    )

    assert validate_item_identification(normalized) is None
    assert normalized["ability_card_id"] == "debt_binding"
    assert normalized["ability_kind"] == "active"
    assert normalized["use_spec"]["message"] == (
        "The {item} names {target}. They are {status}."
    )
    effect = normalized["use_spec"]["effects"][0]
    assert effect["kind"] == "status_nearest"
    assert effect["status"] == "cursed"
    assert effect["duration"] == 6


def test_item_ability_cards_route_specific_semantic_items() -> None:
    debt_ids = [
        card["id"]
        for card in select_item_ability_cards(
            {
                "name": "debtor coin",
                "tags": ["coin", "debt", "law", "curse"],
                "material": "gold",
            },
            {"role": "merchant"},
        )
    ]
    lens_ids = [
        card["id"]
        for card in select_item_ability_cards(
            {
                "name": "crystal ball",
                "tags": ["crystal", "prophecy", "glass"],
                "material": "crystal",
            },
            {"role": "seer"},
        )
    ]

    assert debt_ids[0] == "debt_binding"
    assert lens_ids[0] == "revealing_lens"


def test_item_palettes_expose_prompt_names_and_render_colors() -> None:
    prompt_cards = palette_prompt_cards()

    assert any(card["id"] == "moon_opal" for card in prompt_cards)
    assert palette_label("moon_opal") == "moon opal"
    assert len(palette_colors("moon_opal")) >= 3


def test_identified_inventory_cards_include_palette_label() -> None:
    engine = GameEngine(seed=7, scenario="test_chamber")
    engine.state.inventory["moon glass"] = 1

    identified = engine.identify_inventory_item(
        "moon glass",
        {
            "descriptor": "moonlit",
            "palette_id": "moon_opal",
            "display_name": "moon glass",
            "description": "A moonlit sliver.",
            "ability_summary": "Use it to restore mana.",
            "tags": ["moon", "glass"],
            "ability_kind": "active",
            "use_spec": {
                "effects": [{"kind": "restore_mana", "amount": 4}],
                "message": "The {item} rings softly. You recover {amount} mana.",
                "failure": "Your mana is already full.",
                "consume_on_use": False,
                "charges": 3,
            },
        },
        npc_name="Marta Glass",
        fee=5,
        value_after=22,
        base_value=18,
    )
    assert identified is not None

    card = next(
        item
        for item in equipment_inventory_view(engine)["items"]
        if item["name"] == identified
    )

    assert card["palette_label"] == "moon opal"
    assert "moon opal" in inventory_item_summary(card)
    assert "moon opal" not in inventory_item_summary(card, include_palette_label=False)
    assert "palette: moon opal" in "\n".join(describe_reagents(engine))
