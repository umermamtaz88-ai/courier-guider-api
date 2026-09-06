import pytest

from app.ai.memory.long_memory import ALLOWED_KEYS, LongMemoryService


def test_allowed_memory_keys():
    assert "preferred_priority" in ALLOWED_KEYS
    assert "uses_cod" in ALLOWED_KEYS


def test_infer_preferences():
    svc = LongMemoryService(db=None)  # type: ignore[arg-type]
    updates = svc.infer_from_message(
        "I prefer cheaper shipping with COD",
        {"origin": "Lahore", "product": "clothing", "cod": True},
    )
    keys = [u[0] for u in updates]
    assert "preferred_priority" in keys
    assert "uses_cod" in keys
