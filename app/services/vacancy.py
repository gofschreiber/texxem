"""Vacancy rule (spec 3.5): days without an active tenancy are derived, never stored."""

from datetime import date, timedelta


def vacancy_periods(
    available_from: date, tenancies: list[tuple[date, date | None]], today: date
) -> list[tuple[date, date | None]]:
    """Return vacancy periods as (from, to) tuples; ``to`` is None for an ongoing vacancy.

    ``tenancies`` are (move-in, move-out) pairs, move-out None meaning open-ended.
    """
    periods: list[tuple[date, date | None]] = []
    cursor = available_from
    for move_in, move_out in sorted(tenancies, key=lambda t: t[0]):
        if move_in > cursor:
            periods.append((cursor, move_in - timedelta(days=1)))
        if move_out is None:
            return periods
        cursor = max(cursor, move_out + timedelta(days=1))
    if cursor <= today:
        periods.append((cursor, None))
    return periods
