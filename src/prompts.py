from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text().strip()
