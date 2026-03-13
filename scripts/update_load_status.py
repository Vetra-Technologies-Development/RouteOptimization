"""Update loadboard_loads status based on dates and action."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.dependencies import get_supabase_client


def _calculate_status(row: Dict[str, Any]) -> str:
    action_value = row.get("action")
    if action_value == "deleted":
        return "inactive"

    start_dt = row.get("origin_pickup_local") or row.get("origin_pickup_date")
    end_dt = (
        row.get("origin_pickup_local_end")
        or row.get("destination_delivery_local_end")
        or row.get("origin_pickup_date_end")
        or row.get("destination_delivery_date_end")
    )
    if end_dt is None:
        end_dt = start_dt

    if not start_dt:
        return "inactive"

    try:
        pacific_tz = ZoneInfo("America/Los_Angeles")
    except ZoneInfoNotFoundError:
        pacific_tz = timezone.utc
    today = datetime.now(tz=pacific_tz).date()

    if isinstance(end_dt, str):
        try:
            end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
        except ValueError:
            return "inactive"

    if isinstance(end_dt, datetime) and end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=pacific_tz)

    if not isinstance(end_dt, datetime):
        return "inactive"

    compare_date = end_dt.astimezone(pacific_tz).date()
    return "active" if compare_date >= today else "inactive"


def _fetch_batch(client, start: int, end: int) -> List[Dict[str, Any]]:
    result = (
        client.table("loadboard_loads")
        .select(
            "unique_id,action,status,origin_pickup_date,origin_pickup_date_end,destination_delivery_date_end,"
            "origin_pickup_local,origin_pickup_local_end,destination_delivery_local_end",
        )
        .range(start, end)
        .execute()
    )
    return result.data or []


def main() -> None:
    client = get_supabase_client()
    if not client:
        raise SystemExit("Supabase client not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

    batch_size = 500
    updated = 0

    count_result = client.table("loadboard_loads").select("unique_id", count="exact").execute()
    total_count = count_result.count if hasattr(count_result, "count") else len(count_result.data or [])

    offset = 0
    while offset < total_count:
        end_index = min(total_count - 1, offset + batch_size - 1)
        rows = _fetch_batch(client, offset, end_index)
        if not rows:
            break
        for row in rows:
            new_status = _calculate_status(row)
            if row.get("status") != new_status:
                client.table("loadboard_loads").update({"status": new_status}).eq("unique_id", row["unique_id"]).execute()
                updated += 1
        offset += batch_size

    print(f"Status update complete. Updated {updated} rows.")


if __name__ == "__main__":
    main()
