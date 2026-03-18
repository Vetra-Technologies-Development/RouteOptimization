"""Backfill geolocation_cache from loadboard_loads."""
from __future__ import annotations

import sys
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config.settings import settings
from app.dependencies import get_supabase_client
from app.utils.mapbox import build_address, geocode_location


def _fetch_load_locations(client, start: int, end: int) -> List[Dict[str, Optional[str]]]:
    result = (
        client.table("loadboard_loads")
        .select(
            "origin_city,origin_state,origin_postcode,origin_country,"
            "destination_city,destination_state,destination_postcode,destination_country"
        )
        .range(start, end)
        .execute()
    )
    return result.data or []


def _fetch_existing_keys(client, start: int, end: int) -> List[str]:
    result = (
        client.table("geolocation_cache")
        .select("key")
        .range(start, end)
        .execute()
    )
    rows = result.data or []
    return [row.get("key") for row in rows if row.get("key")]


def _build_key(city: Optional[str], state: Optional[str], postcode: Optional[str], country: Optional[str]) -> Optional[str]:
    address = build_address(city, state, postcode, country)
    if not address:
        return None
    return address.lower()


def _upsert_with_retry(client, record: Dict[str, Any], max_retries: int = 5) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            client.table("geolocation_cache").upsert(record, on_conflict="key").execute()
            return True
        except Exception as exc:
            wait = min(10, 1.5 ** attempt)
            print(f"Upsert failed (attempt {attempt}/{max_retries}): {exc}. Retrying in {wait:.1f}s...")
            sleep(wait)
    return False


def main() -> None:
    client = get_supabase_client()
    if not client:
        raise SystemExit("Supabase client not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

    if not settings.MAPBOX_API_KEY:
        raise SystemExit("MAPBOX_API_KEY is required for geocoding.")

    # Collect unique location keys from loadboard_loads
    unique_locations: Dict[str, Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]] = {}
    batch_size = 500
    offset = 0

    count_result = client.table("loadboard_loads").select("unique_id", count="exact").execute()
    total_count = count_result.count if hasattr(count_result, "count") else len(count_result.data or [])

    while offset < total_count:
        end_index = min(total_count - 1, offset + batch_size - 1)
        rows = _fetch_load_locations(client, offset, end_index)
        if not rows:
            break
        for row in rows:
            for prefix in ("origin", "destination"):
                key = _build_key(
                    row.get(f"{prefix}_city"),
                    row.get(f"{prefix}_state"),
                    row.get(f"{prefix}_postcode"),
                    row.get(f"{prefix}_country"),
                )
                if key and key not in unique_locations:
                    unique_locations[key] = (
                        row.get(f"{prefix}_city"),
                        row.get(f"{prefix}_state"),
                        row.get(f"{prefix}_postcode"),
                        row.get(f"{prefix}_country"),
                    )
        offset += batch_size

    # Load existing keys from geolocation_cache
    existing_keys: Set[str] = set()
    offset = 0
    while True:
        keys = _fetch_existing_keys(client, offset, offset + batch_size - 1)
        if not keys:
            break
        existing_keys.update(keys)
        offset += batch_size

    missing_keys = [key for key in unique_locations.keys() if key not in existing_keys]
    print(f"Found {len(unique_locations)} unique locations, {len(missing_keys)} missing in cache.")

    updated = 0
    failed = 0
    for key in missing_keys:
        city, state, postcode, country = unique_locations[key]
        address = build_address(city, state, postcode, country)
        if not address:
            continue
        coords = geocode_location(address, settings.MAPBOX_API_KEY)
        if not coords:
            continue
        record = {
            "key": key,
            "city": city,
            "state": state,
            "postcode": postcode,
            "country": country,
            "latitude": coords[0],
            "longitude": coords[1],
        }
        if _upsert_with_retry(client, record):
            updated += 1
        else:
            failed += 1
        if updated % 50 == 0:
            print(f"Cached {updated} locations...")
        sleep(0.1)

    print(f"Geolocation cache backfill complete. Added {updated} new locations, {failed} failed.")


if __name__ == "__main__":
    main()
