"""LoadBoard Network service for processing load requests."""
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.config.settings import settings
from app.services.supabase_service import SupabaseService
from app.utils.distance import haversine_distance
from app.utils.mapbox import build_address, geocode_location, route_distance_miles
from app.utils.parsers import parse_lbn_xml

logger = logging.getLogger(__name__)


class LoadBoardService:
    """Service for processing LoadBoard Network requests."""
    
    def __init__(self, supabase_service: SupabaseService):
        """Initialize with Supabase service."""
        self.supabase_service = supabase_service

    def _parse_rate_value(self, rate_value: Optional[str]) -> Optional[float]:
        if not rate_value:
            return None
        cleaned = "".join(ch for ch in rate_value if ch.isdigit() or ch == "." or ch == "-")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return None

    def _is_valid_coord(self, value: Optional[float]) -> bool:
        return value is not None and value != 0

    def _enrich_load_with_geo(self, load_data: Dict[str, Any]) -> None:
        mapbox_key = settings.MAPBOX_API_KEY

        origin_lat = load_data.get("origin_latitude")
        origin_lon = load_data.get("origin_longitude")
        dest_lat = load_data.get("destination_latitude")
        dest_lon = load_data.get("destination_longitude")

        if mapbox_key:
            try:
                if not (self._is_valid_coord(origin_lat) and self._is_valid_coord(origin_lon)):
                    address = build_address(
                        load_data.get("origin_city"),
                        load_data.get("origin_state"),
                        load_data.get("origin_postcode"),
                        load_data.get("origin_country"),
                    )
                    if address:
                        coords = geocode_location(address, mapbox_key)
                        if coords:
                            origin_lat, origin_lon = coords
                            load_data["origin_latitude"] = origin_lat
                            load_data["origin_longitude"] = origin_lon

                if not (self._is_valid_coord(dest_lat) and self._is_valid_coord(dest_lon)):
                    address = build_address(
                        load_data.get("destination_city"),
                        load_data.get("destination_state"),
                        load_data.get("destination_postcode"),
                        load_data.get("destination_country"),
                    )
                    if address:
                        coords = geocode_location(address, mapbox_key)
                        if coords:
                            dest_lat, dest_lon = coords
                            load_data["destination_latitude"] = dest_lat
                            load_data["destination_longitude"] = dest_lon
            except Exception as exc:
                logger.warning(f"Mapbox geocoding failed: {exc}")

        distance_value = load_data.get("distance")
        if not distance_value or distance_value == 0:
            computed_distance = None
            if self._is_valid_coord(origin_lat) and self._is_valid_coord(origin_lon) and self._is_valid_coord(dest_lat) and self._is_valid_coord(dest_lon):
                if mapbox_key:
                    try:
                        computed_distance = route_distance_miles(origin_lat, origin_lon, dest_lat, dest_lon, mapbox_key)
                    except Exception as exc:
                        logger.warning(f"Mapbox routing failed: {exc}")
                if not computed_distance:
                    computed_distance = haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
            if computed_distance:
                load_data["distance"] = round(computed_distance, 2)

        rate_value = self._parse_rate_value(load_data.get("rate"))
        distance_value = load_data.get("distance")
        if rate_value is not None and distance_value:
            load_data["rpm"] = round(rate_value / float(distance_value), 4)
    
    def process_xml_request(self, xml_content: str) -> Tuple[str, int]:
        """
        Process LoadBoard Network XML request.
        
        Returns:
            Tuple of (response_message, success_count)
        """
        try:
            # Parse XML
            parsed_data = parse_lbn_xml(xml_content)
            
            account_data = parsed_data['account']
            operation = parsed_data['operation']
            loads = parsed_data['loads']
            
            if not loads:
                logger.warning("No loads found in request")
                return "Data format incorrect", 0
            
            success_count = 0
            
            if operation == 'post':
                # Process PostLoads
                for load_data in loads:
                    try:
                        self._enrich_load_with_geo(load_data)
                        if self.supabase_service.save_load(account_data, load_data, operation):
                            success_count += 1
                    except Exception as e:
                        logger.error(f"Error processing load: {e}", exc_info=True)
                        continue
                
                logger.info(f"Successfully processed {success_count}/{len(loads)} loads")
                return "Successfully posted", success_count
            
            elif operation == 'remove':
                # Process RemoveLoads
                missing_ids: List[str] = []
                for load_data in loads:
                    try:
                        removed, message = self.supabase_service.remove_load(account_data, load_data)
                        if removed:
                            success_count += 1
                        else:
                            if "ID does not exist" in message:
                                missing_ids.append(message.replace("ID does not exist: ", ""))
                    except Exception as e:
                        logger.error(f"Error processing remove load: {e}", exc_info=True)
                        continue
                
                logger.info(f"Successfully removed {success_count}/{len(loads)} loads")
                if missing_ids and success_count == 0:
                    return f"ID does not exist: {', '.join(missing_ids)}", success_count
                if missing_ids:
                    return f"Removed {success_count}, missing: {', '.join(missing_ids)}", success_count
                return "Successfully removed", success_count
            
            else:
                return "Data format incorrect", 0
                
        except ValueError as e:
            logger.error(f"XML parsing error: {e}")
            return f"Data invalid: {str(e)}", 0
        except Exception as e:
            logger.error(f"Error processing LoadBoard Network request: {e}", exc_info=True)
            return f"Error: {str(e)}", 0

