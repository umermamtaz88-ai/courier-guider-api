def is_duplicate(existing_hash: str | None, new_hash: str) -> bool:
    return bool(existing_hash and existing_hash == new_hash)
