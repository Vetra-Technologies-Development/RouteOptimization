"""Convert load postings CSV into loadboard_loads format with shifted dates."""
from __future__ import annotations

import argparse
import csv
import os
import sys
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple


INPUT_DATE_FIELDS = [
    "origin-date-start",
    "destination-date-start",
    "postedAt",
    "createdAt",
    "updatedAt",
]


OUTPUT_COLUMNS: List[str] = [
    "unique_id",
    "user_id",
    "user_name",
    "company_name",
    "contact_name",
    "contact_phone",
    "contact_fax",
    "contact_email",
    "mc_number",
    "dot_number",
    "tracking_number",
    "load_id",
    "action",
    "origin_city",
    "origin_state",
    "origin_postcode",
    "origin_county",
    "origin_country",
    "origin_latitude",
    "origin_longitude",
    "origin_pickup_date",
    "origin_pickup_date_end",
    "origin_pickup_local",
    "origin_pickup_local_end",
    "origin_pickup_pst",
    "origin_pickup_pst_end",
    "destination_city",
    "destination_state",
    "destination_postcode",
    "destination_county",
    "destination_country",
    "destination_latitude",
    "destination_longitude",
    "destination_delivery_date",
    "destination_delivery_date_end",
    "destination_delivery_local",
    "destination_delivery_local_end",
    "destination_delivery_pst",
    "destination_delivery_pst_end",
    "equipment",
    "full_load",
    "length",
    "width",
    "height",
    "weight",
    "load_count",
    "stops",
    "distance",
    "rate",
    "rpm",
    "comment",
    "created_at",
    "updated_at",
]


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.utils.mapbox import build_address, geocode_location
except Exception:  # pragma: no cover
    build_address = None
    geocode_location = None


def parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_iso(value: Optional[datetime]) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def coerce_float(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def coerce_int(value: str) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def build_target_origin_dt(original_origin: datetime, target_date: datetime) -> datetime:
    if original_origin.tzinfo:
        target_date = target_date.replace(tzinfo=original_origin.tzinfo)
    return original_origin.replace(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
    )


def shift_dates(row: Dict[str, str], target_date: datetime) -> Dict[str, str]:
    origin_value = parse_iso(row.get("origin-date-start", ""))
    if not origin_value:
        return row
    target_origin = build_target_origin_dt(origin_value, target_date)
    delta: timedelta = target_origin - origin_value
    updated = dict(row)
    for field in INPUT_DATE_FIELDS:
        parsed = parse_iso(row.get(field, ""))
        if parsed:
            updated[field] = format_iso(parsed + delta)
    return updated


def _random_token() -> str:
    return uuid4().hex


def convert_row(
    row: Dict[str, str],
    target_date: datetime,
    randomize_ids: bool,
) -> Dict[str, str]:
    row = shift_dates(row, target_date)
    user_id = (row.get("userID") or "").strip()
    tracking_number = (row.get("tracking-number") or "").strip()
    if randomize_ids:
        user_id = _random_token()
    unique_id = f"{user_id}_{tracking_number}" if user_id and tracking_number else ""
    loadsize = (row.get("loadsize") or "").strip().lower()
    full_load = "true" if loadsize == "full" else "false"
    company_name = (row.get("CompanyName") or "").strip()
    load_id = tracking_number
    if randomize_ids:
        company_name = f"Company-{_random_token()[:12]}"
        load_id = _random_token()

    distance_value = coerce_float(row.get("distance", ""))
    rate_value = coerce_float(row.get("rate", ""))
    rpm_value: Optional[float] = None
    if rate_value is not None and distance_value:
        rpm_value = round(rate_value / distance_value, 4)

    output = {
        "unique_id": unique_id,
        "user_id": user_id,
        "user_name": "",
        "company_name": company_name,
        "contact_name": (row.get("ContactName") or "").strip(),
        "contact_phone": (row.get("ContactPhone") or "").strip(),
        "contact_fax": (row.get("ContactFax") or "").strip(),
        "contact_email": (row.get("ContactEmail") or "").strip(),
        "mc_number": (row.get("mcNumber") or "").strip(),
        "dot_number": (row.get("dotNumber") or "").strip(),
        "tracking_number": tracking_number,
        "load_id": load_id,
        "action": (row.get("action") or "").strip(),
        "origin_city": (row.get("origin-city") or "").strip(),
        "origin_state": (row.get("origin-state") or "").strip(),
        "origin_postcode": "",
        "origin_county": "",
        "origin_country": "",
        "origin_latitude": "",
        "origin_longitude": "",
        "origin_pickup_date": row.get("origin-date-start", ""),
        "origin_pickup_date_end": "",
        "origin_pickup_local": "",
        "origin_pickup_local_end": "",
        "origin_pickup_pst": "",
        "origin_pickup_pst_end": "",
        "destination_city": (row.get("destination-city") or "").strip(),
        "destination_state": (row.get("destination-state") or "").strip(),
        "destination_postcode": "",
        "destination_county": "",
        "destination_country": "",
        "destination_latitude": "",
        "destination_longitude": "",
        "destination_delivery_date": row.get("destination-date-start", ""),
        "destination_delivery_date_end": "",
        "destination_delivery_local": "",
        "destination_delivery_local_end": "",
        "destination_delivery_pst": "",
        "destination_delivery_pst_end": "",
        "equipment": (row.get("equipment") or "").strip(),
        "full_load": full_load,
        "length": row.get("length", "").strip(),
        "width": "",
        "height": "",
        "weight": row.get("weight", "").strip(),
        "load_count": row.get("load-count", "").strip(),
        "stops": row.get("stops", "").strip(),
        "distance": row.get("distance", "").strip(),
        "rate": row.get("rate", "").strip(),
        "rpm": "" if rpm_value is None else f"{rpm_value:.4f}",
        "comment": row.get("comment", "").strip(),
        "created_at": row.get("createdAt", ""),
        "updated_at": row.get("updatedAt", ""),
    }
    return output


def maybe_geocode(
    row: Dict[str, str],
    output: Dict[str, str],
    mapbox_key: Optional[str],
    cache: Dict[str, Tuple[float, float]],
) -> None:
    if not mapbox_key or not build_address or not geocode_location:
        return

    def resolve_address(prefix: str) -> Optional[str]:
        return build_address(
            row.get(f"{prefix}-city"),
            row.get(f"{prefix}-state"),
            row.get(f"{prefix}-postcode"),
            row.get(f"{prefix}-country"),
        )

    for prefix, lat_key, lon_key in [
        ("origin", "origin_latitude", "origin_longitude"),
        ("destination", "destination_latitude", "destination_longitude"),
    ]:
        address = resolve_address(prefix)
        if not address:
            continue
        if address in cache:
            lat, lon = cache[address]
        else:
            coords = geocode_location(address, mapbox_key)
            if not coords:
                continue
            lat, lon = coords
            cache[address] = (lat, lon)
        output[lat_key] = f"{lat:.6f}"
        output[lon_key] = f"{lon:.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert load postings CSV to loadboard_loads format.")
    parser.add_argument("--input", required=True, help="Path to input CSV file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--target-date", default="2026-02-17", help="Target origin date (YYYY-MM-DD).")
    parser.add_argument("--geocode", action="store_true", help="Fill lat/lon using Mapbox geocoding.")
    parser.add_argument("--mapbox-key", default=os.getenv("MAPBOX_API_KEY", ""), help="Mapbox API key.")
    parser.add_argument("--randomize-ids", action="store_true", help="Randomize user_id, company_name, and load_id.")
    args = parser.parse_args()

    target_date = datetime.fromisoformat(args.target_date)
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mapbox_key = args.mapbox_key.strip() if args.mapbox_key else ""
    cache: Dict[str, Tuple[float, float]] = {}

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        with output_path.open("w", encoding="utf-8", newline="") as out_handle:
            writer = csv.DictWriter(out_handle, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for row in reader:
                output = convert_row(row, target_date, args.randomize_ids)
                if args.geocode:
                    maybe_geocode(row, output, mapbox_key, cache)
                writer.writerow(output)


if __name__ == "__main__":
    main()

