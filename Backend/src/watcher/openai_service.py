from __future__ import annotations

import os
from pathlib import Path


class OpenAIConfigError(RuntimeError):
    """Raised when OpenAI credentials/deps are not set up correctly."""


_DOTENV_LOADED = False


def _load_env_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    # Load `.env` from project root (two levels up from this file).
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=dotenv_path)
    except Exception:
        try:
            if dotenv_path.exists():
                for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    key = k.strip()
                    val = v.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

    _DOTENV_LOADED = True


def _get_api_key() -> str:
    _load_env_once()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIConfigError(
            "Missing OPENAI_API_KEY. Create a .env file or set OPENAI_API_KEY in your environment."
        )
    return api_key


def generate_text(prompt: str, *, model: str = "gpt-4o-mini") -> str:
    """Minimal OpenAI wrapper."""
    api_key = _get_api_key()

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise OpenAIConfigError("OpenAI SDK not installed. Run: pip install openai") from e

    client = OpenAI(api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        content = completion.choices[0].message.content
        return (content or "").strip()
    except Exception as e:
        status_code = getattr(e, "status_code", None)
        msg = str(e)
        if status_code == 429 or "insufficient_quota" in msg or "exceeded your current quota" in msg:
            raise OpenAIConfigError(
                "OpenAI returned 429 (insufficient quota). Check billing, then re-run."
            ) from e
        if status_code in (401, 403) or "Incorrect API key" in msg or "invalid_api_key" in msg:
            raise OpenAIConfigError(
                "OpenAI authentication failed (check OPENAI_API_KEY), then re-run."
            ) from e
        raise
