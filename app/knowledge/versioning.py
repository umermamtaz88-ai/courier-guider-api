from datetime import UTC, datetime


def mark_superseded(status: str) -> str:
    return "SUPERSEDED" if status == "ACTIVE" else status


def new_version_status() -> str:
    return "ACTIVE"


def version_metadata(*, previous_version: int | None = None) -> dict:
    return {
        "version": (previous_version or 0) + 1,
        "last_changed_at": datetime.now(UTC).isoformat(),
    }
