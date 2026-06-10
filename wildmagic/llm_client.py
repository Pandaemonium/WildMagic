from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


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
        
    print(f"Ollama server not detected at {base_url}. Attempting to start 'ollama serve' in the background...")
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True
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


def ollama_timeout_seconds() -> float:
    value = os.environ.get("WILDMAGIC_OLLAMA_TIMEOUT", "180")
    try:
        timeout = float(value)
    except ValueError:
        return 180.0
    return max(5.0, timeout)


def ollama_num_predict() -> int:
    value = os.environ.get("WILDMAGIC_OLLAMA_NUM_PREDICT", "1024")
    try:
        parsed = int(value)
    except ValueError:
        return 800
    return max(128, min(4096, parsed))


def ollama_num_ctx() -> int:
    """Context window size (prompt + response, in tokens).

    Ollama defaults to 2048 when a model's Modelfile doesn't set num_ctx, and
    qwen3:8b doesn't. Our system prompt alone is ~3,600 tokens, so the default
    silently truncates it from the conversation — the model then sees only a
    JSON blob with no instructions and echoes it back instead of resolving the
    spell. Default high enough to comfortably fit prompt + context + response.
    """
    value = os.environ.get("WILDMAGIC_OLLAMA_NUM_CTX", "8192")
    try:
        parsed = int(value)
    except ValueError:
        return 8192
    return max(2048, min(32768, parsed))


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


def ollama_thinking_enabled() -> bool:
    value = os.environ.get("WILDMAGIC_OLLAMA_THINK", "0").lower().strip()
    return value in {"1", "true", "yes", "on"}


def ollama_json_format_enabled() -> bool:
    value = os.environ.get("WILDMAGIC_OLLAMA_FORMAT", "json").lower().strip()
    return value in {"1", "true", "yes", "on", "json"}


def ollama_town_num_predict() -> int:
    value = os.environ.get("WILDMAGIC_TOWN_NUM_PREDICT", "2000")
    try:
        parsed = int(value)
    except ValueError:
        return 2000
    return max(256, min(8192, parsed))


def ollama_num_gpu() -> int:
    value = os.environ.get("WILDMAGIC_OLLAMA_NUM_GPU", "999")
    try:
        parsed = int(value)
    except ValueError:
        return 999
    return max(0, min(999, parsed))


def ollama_resolution_attempts() -> int:
    value = os.environ.get("WILDMAGIC_OLLAMA_RESOLUTION_ATTEMPTS", "2")
    try:
        parsed = int(value)
    except ValueError:
        return 2
    return max(1, min(4, parsed))


def fetch_ollama_models(base_url: str | None = None) -> list[str]:
    """Return sorted list of model names available from Ollama. Empty list on failure."""
    url = normalize_ollama_url(base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ensure_ollama_running(url)
    try:
        req = urllib.request.Request(f"{url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []
