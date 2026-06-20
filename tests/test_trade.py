from __future__ import annotations

from wildmagic.prompts import TRADE_SYSTEM_PROMPT


def test_trade_prompt_treats_direct_merchant_requests_as_actionable() -> None:
    prompt = TRADE_SYSTEM_PROMPT.lower()

    assert "directly asks to buy" in prompt
    assert "wares_for_sale" in prompt
    assert "invent it" in prompt
