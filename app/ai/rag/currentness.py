from datetime import UTC, datetime

from app.config import get_settings


def authority_score(authority_level: int) -> float:
    """Lower authority_level number = higher trust (1 is best)."""
    return max(0.0, min(1.0, (6 - authority_level) / 5))


def currentness_score(
    effective_from: datetime | None,
    effective_to: datetime | None,
    as_of: datetime | None = None,
    *,
    last_verified_at: datetime | None = None,
    stale_days: int | None = None,
) -> float:
    """
    Score currentness for ranking.

    1.0  = current (within stale window / has effective_from and not expired)
    0.7  = recent but aging
    0.4  = unknown (no dates) — do NOT treat as recent
    0.2  = stale (old but not expired)
    0.0  = not yet effective or expired
    """
    as_of = as_of or datetime.now(UTC)
    max_age = stale_days if stale_days is not None else get_settings().rag_stale_days

    if effective_from and effective_from > as_of:
        return 0.0
    if effective_to and effective_to < as_of:
        return 0.0  # expired

    ref = last_verified_at or effective_from
    if ref is None:
        return 0.4  # unknown — not "recent"

    age_days = (as_of - ref).days
    if age_days <= 30:
        return 1.0
    if age_days <= max_age:
        return 0.7
    return 0.2


def freshness_label(
    effective_from: datetime | None,
    effective_to: datetime | None,
    *,
    last_verified_at: datetime | None = None,
    stale_days: int | None = None,
    as_of: datetime | None = None,
) -> str:
    """Canonical labels: current | recent | stale | expired | unknown."""
    as_of = as_of or datetime.now(UTC)
    max_age = stale_days if stale_days is not None else get_settings().rag_stale_days

    if effective_to and effective_to < as_of:
        return "expired"
    if effective_from and effective_from > as_of:
        return "unknown"

    ref = last_verified_at or effective_from
    if ref is None:
        return "unknown"

    age_days = (as_of - ref).days
    if age_days <= 30:
        return "current"
    if age_days <= max_age:
        return "recent"
    return "stale"


def is_currently_applicable(
    effective_from: datetime | None,
    effective_to: datetime | None,
    as_of: datetime | None = None,
) -> bool:
    return currentness_score(effective_from, effective_to, as_of) >= 0.5
