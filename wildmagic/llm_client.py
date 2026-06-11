from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def _first_env(names: list[str], default: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _purpose_key(purpose: str | None) -> str | None:
    if not purpose:
        return None
    normalized = re.sub(r"[^A-Z0-9]+", "_", purpose.upper()).strip("_")
    aliases = {
        "SPELL": "WILD",
        "WILD_MAGIC": "WILD",
        "MAGIC": "WILD",
        "NPC_DIALOGUE": "DIALOGUE",
        "BACKGROUND_TOWN": "TOWN",
        "TOWN_GENERATION": "TOWN",
    }
    return aliases.get(normalized, normalized)


def _route_key(purpose: str | None) -> str | None:
    key = _purpose_key(purpose)
    if key in {"WILD", "DIALOGUE", "TRADE"}:
        return "URGENT"
    if key == "TOWN":
        return "BACKGROUND"
    return None


def _scoped_env_names(purpose: str | None, suffix: str) -> list[str]:
    names: list[str] = []
    key = _purpose_key(purpose)
    route = _route_key(purpose)
    if key:
        names.append(f"WILDMAGIC_{key}_{suffix}")
    if route:
        names.append(f"WILDMAGIC_{route}_{suffix}")
    names.append(f"WILDMAGIC_{suffix}")
    return names


def _int_env(names: list[str], default: int, minimum: int, maximum: int) -> int:
    value = _first_env(names, str(default))
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _float_env(names: list[str], default: float, minimum: float, maximum: float) -> float:
    value = _first_env(names, str(default))
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _bool_env(names: list[str], default: str) -> bool:
    value = _first_env(names, default).lower().strip()
    return value in {"1", "true", "yes", "on", "json"}


def parse_ollama_error_body(body: str) -> str:
    stripped = body.strip()
    if not stripped:
        return ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped[:500]
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, str):
            return error
    return stripped[:500]


def ensure_ollama_running(base_url: str) -> bool:
    """Check if Ollama is running at base_url. If not, try to start it in the background
    and wait up to 12 seconds for it to become responsive."""
    import socket
    import subprocess
    import time
    from urllib.parse import urlparse
    
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 11434
    
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (OSError, ConnectionRefusedError):
        pass
        
    auto_start = os.environ.get("WILDMAGIC_OLLAMA_AUTOSTART", "1").lower().strip()
    if auto_start in {"0", "false", "no", "off"}:
        print(f"Ollama server not detected at {base_url}. Autostart is disabled.")
        return False

    print(f"Ollama server not detected at {base_url}. Attempting to start 'ollama serve' in the background...")
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        child_env = os.environ.copy()
        child_env["OLLAMA_HOST"] = base_url
            
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
            env=child_env,
        )
    except FileNotFoundError:
        print("Ollama command-line tool not found on PATH. Cannot auto-start server.")
        return False
        
    for attempt in range(1, 13):
        time.sleep(1.0)
        try:
            with socket.create_connection((host, port), timeout=1):
                # Verify HTTP response
                req = urllib.request.Request(f"{base_url}/api/tags")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        print(f"Ollama server successfully started and responsive after {attempt}s.")
                        return True
        except Exception:
            pass
            
    print("Ollama server failed to start or respond within 12 seconds.")
    return False


def _post_ollama_chat(base_url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    """Shared low-level Ollama /api/chat POST, used by every Ollama-backed provider
    (wild magic resolution, NPC dialogue, and any future LLM-driven subsystem) so
    that swapping models per-purpose never requires duplicating HTTP plumbing."""
    ensure_ollama_running(base_url)
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = parse_ollama_error_body(body)
        raise ValueError(f"Ollama HTTP {exc.code}: {detail or exc.reason}") from exc


def strip_thinking(raw: str) -> str:
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()


def extract_thinking(raw: str) -> str | None:
    if not raw:
        return None
    match = re.search(r"<think>(.*?)</think>", raw, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    thought = match.group(1).strip()
    return thought or None


def normalize_ollama_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def ollama_host(purpose: str | None = None) -> str:
    """Return the Ollama endpoint for a provider purpose.

    For a town request, precedence is:
    WILDMAGIC_TOWN_OLLAMA_HOST -> WILDMAGIC_BACKGROUND_OLLAMA_HOST ->
    WILDMAGIC_OLLAMA_HOST -> OLLAMA_HOST -> localhost:11434.
    """
    names = _scoped_env_names(purpose, "OLLAMA_HOST") + ["OLLAMA_HOST"]
    return normalize_ollama_url(_first_env(names, DEFAULT_OLLAMA_HOST))


def ollama_timeout_seconds(purpose: str | None = None) -> float:
    return _float_env(_scoped_env_names(purpose, "OLLAMA_TIMEOUT"), 180.0, 5.0, 1800.0)


def ollama_num_predict() -> int:
    value = os.environ.get("WILDMAGIC_OLLAMA_NUM_PREDICT", "1024")
    try:
        parsed = int(value)
    except ValueError:
        return 800
    return max(128, min(4096, parsed))


def ollama_num_ctx(purpose: str | None = None) -> int:
    """Context window size (prompt + response, in tokens).

    Ollama defaults to 2048 when a model's Modelfile doesn't set num_ctx, and
    qwen3:8b doesn't. Our system prompt alone is ~3,600 tokens, so the default
    silently truncates it from the conversation — the model then sees only a
    JSON blob with no instructions and echoes it back instead of resolving the
    spell. Default high enough to comfortably fit prompt + context + response.
    """
    return _int_env(_scoped_env_names(purpose, "OLLAMA_NUM_CTX"), 16384, 2048, 32768)


def ollama_temperature() -> float:
    value = os.environ.get("WILDMAGIC_OLLAMA_TEMPERATURE", "0.25")
    try:
        parsed = float(value)
    except ValueError:
        return 0.25
    return max(0.0, min(1.5, parsed))


def ollama_dialogue_temperature() -> float:
    value = os.environ.get("WILDMAGIC_DIALOGUE_TEMPERATURE", "0.7")
    try:
        parsed = float(value)
    except ValueError:
        return 0.7
    return max(0.0, min(1.5, parsed))


def ollama_dialogue_num_predict() -> int:
    value = os.environ.get("WILDMAGIC_DIALOGUE_NUM_PREDICT", "320")
    try:
        parsed = int(value)
    except ValueError:
        return 200
    return max(32, min(1024, parsed))


def ollama_trade_temperature() -> float:
    value = (
        os.environ.get("WILDMAGIC_TRADE_TEMPERATURE")
        or os.environ.get("WILDMAGIC_DIALOGUE_TEMPERATURE", "0.5")
    )
    try:
        parsed = float(value)
    except ValueError:
        return 0.5
    return max(0.0, min(1.5, parsed))


def ollama_trade_num_predict() -> int:
    value = (
        os.environ.get("WILDMAGIC_TRADE_NUM_PREDICT")
        or os.environ.get("WILDMAGIC_DIALOGUE_NUM_PREDICT", "320")
    )
    try:
        parsed = int(value)
    except ValueError:
        return 320
    return max(32, min(1024, parsed))


def ollama_thinking_enabled(purpose: str | None = None) -> bool:
    return _bool_env(_scoped_env_names(purpose, "OLLAMA_THINK"), "0")


def ollama_json_format_enabled(purpose: str | None = None) -> bool:
    return _bool_env(_scoped_env_names(purpose, "OLLAMA_FORMAT"), "json")


def ollama_town_num_predict() -> int:
    value = os.environ.get("WILDMAGIC_TOWN_NUM_PREDICT", "2000")
    try:
        parsed = int(value)
    except ValueError:
        return 2000
    return max(256, min(8192, parsed))


def ollama_num_gpu(purpose: str | None = None) -> int:
    return _int_env(_scoped_env_names(purpose, "OLLAMA_NUM_GPU"), 999, 0, 999)


def ollama_keep_alive(purpose: str | None = None) -> str:
    return _first_env(_scoped_env_names(purpose, "OLLAMA_KEEP_ALIVE"), "10m")


def ollama_resolution_attempts() -> int:
    value = os.environ.get("WILDMAGIC_OLLAMA_RESOLUTION_ATTEMPTS", "2")
    try:
        parsed = int(value)
    except ValueError:
        return 2
    return max(1, min(4, parsed))


def fetch_ollama_models(base_url: str | None = None, purpose: str | None = "wild") -> list[str]:
    """Return sorted list of model names available from Ollama. Empty list on failure."""
    url = normalize_ollama_url(base_url) if base_url else ollama_host(purpose)
    ensure_ollama_running(url)
    try:
        req = urllib.request.Request(f"{url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []
