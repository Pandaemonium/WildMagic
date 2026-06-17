"""Model-free tests for the lore-card system (docs/LORE_CARDS.md M1).

Covers the access gate, relevance routing, registry validation, the router contract
(failure vs deliberate-empty, unknown-id ignoring, subset invariant), budgets, and tag
normalization. No backend: the generative router is exercised via an injected spy.
"""

from __future__ import annotations

from types import SimpleNamespace

from wildmagic.lore_cards import (
    KNOWN_TAGS,
    LORE_CARDS,
    TAG_ALIASES,
    LoreCard,
    eligible_cards,
    knows,
    normalize_lore_tags,
    prefilter,
    seed_npc_lore,
    select_lore_cards,
)
from wildmagic.lore_router import book_lore_cards, dialogue_lore_cards


class RouteSpy:
    """An injected route_call that records its invocations and returns a fixed result."""

    def __init__(self, result):
        self.result = result
        self.calls: list = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.result


# --------------------------------------------------------------------------------------
# Registry validation
# --------------------------------------------------------------------------------------
def test_registry_names_unique():
    names = [c.name for c in LORE_CARDS]
    assert len(names) == len(set(names))


def test_registry_fields_well_formed():
    for c in LORE_CARDS:
        assert c.threshold >= 0, c.name
        assert c.tags and all(t and t == t.lower() for t in c.tags), c.name
        assert c.triggers and all(t == t.lower() for t in c.triggers), c.name
        assert c.text.strip(), c.name
        assert c.index_line.strip(), c.name


def test_aliases_resolve_to_known_tags():
    for canonical in TAG_ALIASES.values():
        assert canonical in KNOWN_TAGS


# --------------------------------------------------------------------------------------
# Access gate
# --------------------------------------------------------------------------------------
def test_default_zero_gets_exactly_level_0_cards():
    # An empty knower is 0 on every tag, so it reaches precisely the threshold-0 cards.
    assert eligible_cards({}) == [c for c in LORE_CARDS if c.threshold == 0]


def test_access_is_cumulative():
    elig = {c.name for c in eligible_cards({"stalnaz": 1})}
    assert "stalnaz_basics" in elig  # threshold 0
    assert "stalnaz_rule" in elig  # threshold 1
    # A different tradition the knower has no lore in stays at its L0 only.
    assert "crystal_truth" not in elig  # crystal still 0, threshold 1


def test_pure_sum_multi_tag_access():
    card = LoreCard("tc", ("threen", "crystal"), 6, ("x",), "i", "t")
    assert knows({"threen": 6}, card)  # one tag alone meets the sum
    assert knows({"threen": 3, "crystal": 3}, card)
    assert not knows({"threen": 5}, card)  # 5 < 6
    assert not knows({}, card)


# --------------------------------------------------------------------------------------
# Relevance — deterministic path (route_call=None)
# --------------------------------------------------------------------------------------
def test_on_topic_selects_subject_not_neighbors():
    cards = select_lore_cards(
        {"stalnaz": 2}, "why did the queen choose her heiress?", route_call=None
    )
    names = {c.name for c in cards}
    assert "stalnaz_rule" in names
    assert "merfolk_basics" not in names
    assert "brall_basics" not in names


def test_multiple_topics_each_select():
    cards = select_lore_cards(
        {"stalnaz": 1, "crystal": 1},
        "tell me about Stalnaz and its crystals",
        route_call=None,
    )
    names = {c.name for c in cards}
    assert {"stalnaz_basics", "crystal_basics"} <= names


def test_bare_greeting_injects_nothing_and_does_not_route():
    spy = RouteSpy(["stalnaz_rule"])
    cards = select_lore_cards({"stalnaz": 3}, "hello there", route_call=spy)
    assert cards == []
    assert spy.calls == []  # no topical hit -> the router is never even consulted


def test_soft_bias_alone_never_selects_on_greeting():
    # A speaker biased toward their home region still says nothing canonical on a bare hello.
    cards = select_lore_cards(
        {"stalnaz": 3}, "good morning", bias_tags=("stalnaz",), route_call=None
    )
    assert cards == []


# --------------------------------------------------------------------------------------
# Router contract
# --------------------------------------------------------------------------------------
_MANY = "tell me about horses and the empire roads"  # hits monteary + empire_basics + empire_peace


def test_router_fires_only_when_more_hints_than_budget():
    spy = RouteSpy(["empire_basics", "monteary_basics"])
    cards = select_lore_cards({}, _MANY, route_call=spy, max_cards=2)
    assert len(spy.calls) == 1
    assert {c.name for c in cards} == {"empire_basics", "monteary_basics"}


def test_router_unknown_ids_ignored():
    spy = RouteSpy(["bogus_card", "empire_basics"])
    cards = select_lore_cards({}, "horses and empire", route_call=spy, max_cards=1)
    assert {c.name for c in cards} == {"empire_basics"}


def test_router_cannot_leak_card_outside_the_hinted_set():
    # merfolk_basics is eligible (L0) but off-topic, so it never reached the router's menu;
    # naming it must not smuggle it into the result.
    spy = RouteSpy(["merfolk_basics"])
    cards = select_lore_cards({}, "horses and empire", route_call=spy, max_cards=1)
    assert cards == []


def test_router_failure_falls_back_to_ranking():
    spy = RouteSpy(None)  # None == failure
    cards = select_lore_cards({}, "horses and empire", route_call=spy, max_cards=1)
    assert len(cards) == 1  # deterministic fallback still produces a sensible pick


def test_router_deliberate_empty_is_respected():
    spy = RouteSpy([])  # success, found nothing relevant
    cards = select_lore_cards({}, "horses and empire", route_call=spy, max_cards=1)
    assert cards == []


def test_selection_is_always_subset_of_eligible_and_hinted():
    spy = RouteSpy([c.name for c in LORE_CARDS])  # name everything
    cards = select_lore_cards({}, _MANY, route_call=spy, max_cards=5)
    hinted = {c.name for c in prefilter(eligible_cards({}), _MANY, set())}
    assert {c.name for c in cards} <= hinted


# --------------------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------------------
def test_max_cards_budget():
    cards = select_lore_cards({}, _MANY, route_call=None, max_cards=1)
    assert len(cards) == 1


def test_max_chars_budget():
    cards = select_lore_cards({}, _MANY, route_call=None, max_cards=5, max_chars=10)
    assert (
        len(cards) == 1
    )  # first card always admitted; the next exceeds the tiny budget


# --------------------------------------------------------------------------------------
# Tag normalization
# --------------------------------------------------------------------------------------
def test_normalize_lore_tags_maps_and_drops():
    got = normalize_lore_tags(
        ["crystals", "crystal magic", "Stalnazan", "charter law", "not_a_real_tag"]
    )
    assert got == {"crystal", "stalnaz", "charter"}


# --------------------------------------------------------------------------------------
# NPC lore seeding (M2)
# --------------------------------------------------------------------------------------
def test_seed_scholar_in_home_region_is_deep():
    lore = seed_npc_lore("court philosopher", region="Stalnaz")
    assert lore.get("stalnaz") == 3  # scholar archetype


def test_seed_tradition_named_in_role():
    lore = seed_npc_lore("crystal-keyer")
    assert lore.get("crystal") == 1  # commoner floor, but the tradition is recognized


def test_seed_guide_uses_explicit_tags():
    lore = seed_npc_lore("local guide", tags=("stalnaz", "human"))
    assert lore == {"stalnaz": 2}  # "human" is not a lore tag and is dropped


def test_seed_unknown_region_gives_no_seed():
    # A passing tinker in a thematic (non-realm) region knows only the universal L0.
    assert seed_npc_lore("tinker", region="the Saltmarket") == {}


# --------------------------------------------------------------------------------------
# Dialogue selection (M2) — deterministic, no server (mock provider => route_call=None)
# --------------------------------------------------------------------------------------
def test_dialogue_lore_cards_off_when_disabled(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "0")
    prof = SimpleNamespace(lore={"stalnaz": 2}, role="guide")
    cards = dialogue_lore_cards(
        prof, "tell me about the queen", provider_name="mock", region_name="Stalnaz"
    )
    assert cards == []


def test_dialogue_lore_cards_selects_for_local_when_enabled(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "1")
    prof = SimpleNamespace(lore={"stalnaz": 2}, role="guide")
    cards = dialogue_lore_cards(
        prof,
        "why did the queen pick an heiress?",
        provider_name="mock",
        region_name="Stalnaz",
    )
    assert "stalnaz_rule" in {c.name for c in cards}


def test_dialogue_lore_cards_outsider_only_reaches_level_0(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "1")
    # No lore => only L0 cards are eligible, so the deep succession card stays out of reach.
    prof = SimpleNamespace(lore={}, role="tinker")
    cards = dialogue_lore_cards(
        prof,
        "why did the queen pick an heiress?",
        provider_name="mock",
        region_name="the Saltmarket",
    )
    assert "stalnaz_rule" not in {c.name for c in cards}


# --------------------------------------------------------------------------------------
# Book consumer (M3) — deterministic, subjects are authoritative HARD tags
# --------------------------------------------------------------------------------------
def test_book_lore_cards_selected_by_subjects(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "1")
    cards = book_lore_cards(
        ["crystals", "Stalnazan"], "On the Tuning of Resonant Stone"
    )
    names = {c.name for c in cards}
    # An author who knows their subjects deeply reaches the L1 truths, not just L0.
    assert "crystal_truth" in names
    assert "stalnaz_basics" in names
    # ...and stays on-topic: no unrelated realm leaks in.
    assert "merfolk_basics" not in names


def test_book_lore_cards_empty_without_known_subjects(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "1")
    assert book_lore_cards(["cartography", "ink"], "A Ledger of Old Maps") == []


def test_book_lore_cards_off_when_disabled(monkeypatch):
    monkeypatch.setenv("WILDMAGIC_LORE_CARDS_ENABLED", "0")
    assert book_lore_cards(["crystals"], "On Stone") == []
