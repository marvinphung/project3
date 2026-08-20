from __future__ import annotations

from datetime import UTC, datetime, timedelta


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def floor_3h_window(dt: datetime) -> datetime:
    utc_dt = to_utc(dt)
    floored_hour = (utc_dt.hour // 3) * 3
    return utc_dt.replace(hour=floored_hour, minute=0, second=0, microsecond=0)


def get_latest_closed_3h_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current_utc = to_utc(now or datetime.now(UTC))
    current_window_start = floor_3h_window(current_utc)
    window_end = current_window_start
    window_start = window_end - timedelta(hours=3)
    return window_start, window_end


def get_current_or_latest_3h_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current_utc = to_utc(now or datetime.now(UTC))
    window_start = floor_3h_window(current_utc)
    window_end = window_start + timedelta(hours=3)
    return window_start, window_end


def get_utc_3h_windows(start_time: datetime, end_time: datetime) -> list[tuple[datetime, datetime]]:
    current = floor_3h_window(start_time)
    end_utc = to_utc(end_time)
    windows: list[tuple[datetime, datetime]] = []

    while current < end_utc:
        w_end = current + timedelta(hours=3)
        windows.append((current, w_end))
        current = w_end

    return windows
