from __future__ import annotations

import hashlib
from typing import Any


def stable_seed(*parts: Any) -> int:
    """Return a process-stable integer seed for deterministic procedural generation."""
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
