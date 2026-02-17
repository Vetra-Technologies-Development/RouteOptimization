"""Mapbox geocoding and routing utilities."""
from __future__ import annotations

from typing import Optional, Tuple

import requests


def _clean_address(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def build_address(
    city: Optional[str],
    state: Optional[str],
    postcode: Optional[str],
    country: Optional[str],
) -> Optional[str]:
    parts = [
        _clean_address(city),
        _clean_address(state),
        _clean_address(postcode),
        _clean_address(country),
    ]
    parts = [part for part in parts if part]
    return ", ".join(parts) if parts else None


def geocode_location(address: str, access_token: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) for a single address using Mapbox geocoding."""
    if not address or not access_token:
        return None
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{requests.utils.quote(address)}.json"
    params = {
        "access_token": access_token,
        "limit": 1,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features") or []
    if not features:
        return None
    center = features[0].get("center")
    if not center or len(center) < 2:
        return None
    lon, lat = center[0], center[1]
    return (lat, lon)


def route_distance_miles(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    access_token: str,
) -> Optional[float]:
    """Return driving distance in miles using Mapbox Directions API."""
    if not access_token:
        return None
    coordinates = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coordinates}"
    params = {
        "access_token": access_token,
        "overview": "false",
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    routes = payload.get("routes") or []
    if not routes:
        return None
    distance_meters = routes[0].get("distance")
    if distance_meters is None:
        return None
    return float(distance_meters) / 1609.344

