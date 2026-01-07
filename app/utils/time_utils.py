"""Time utility functions."""
from datetime import datetime


def parse_iso_to_minutes(iso_string: str) -> int:
    """Convert ISO 8601 timestamp to minutes from reference time."""
    try:
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        dt = datetime.fromisoformat(iso_string)
        ref_dt = datetime(2025, 11, 20, 0, 0, 0)
        if dt.tzinfo:
            dt_naive = dt.replace(tzinfo=None)
            delta = dt_naive - ref_dt
        else:
            delta = dt - ref_dt
        return int(delta.total_seconds() / 60)
    except:
        return 0

