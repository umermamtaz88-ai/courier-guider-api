from pathlib import Path

PROMPT_VERSION = "courier_guider_v4"
_PROMPT_PATH = Path(__file__).parent / "courier_guider_system.md"


def load_courier_guider_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")
