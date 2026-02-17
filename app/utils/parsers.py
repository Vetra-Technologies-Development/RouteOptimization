"""XML parsing utilities for LoadBoard Network."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:
    PACIFIC_TZ = timezone.utc

STATE_TZ_MAP = {
    # Pacific
    "CA": "America/Los_Angeles",
    "OR": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    "NV": "America/Los_Angeles",
    # Mountain
    "AZ": "America/Phoenix",
    "CO": "America/Denver",
    "ID": "America/Denver",
    "MT": "America/Denver",
    "NM": "America/Denver",
    "UT": "America/Denver",
    "WY": "America/Denver",
    # Central
    "AL": "America/Chicago",
    "AR": "America/Chicago",
    "IA": "America/Chicago",
    "IL": "America/Chicago",
    "KS": "America/Chicago",
    "LA": "America/Chicago",
    "MN": "America/Chicago",
    "MO": "America/Chicago",
    "MS": "America/Chicago",
    "ND": "America/Chicago",
    "NE": "America/Chicago",
    "OK": "America/Chicago",
    "SD": "America/Chicago",
    "TN": "America/Chicago",
    "TX": "America/Chicago",
    "WI": "America/Chicago",
    # Eastern
    "CT": "America/New_York",
    "DC": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",
    "GA": "America/New_York",
    "IN": "America/New_York",
    "KY": "America/New_York",
    "MA": "America/New_York",
    "MD": "America/New_York",
    "ME": "America/New_York",
    "MI": "America/New_York",
    "NC": "America/New_York",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NY": "America/New_York",
    "OH": "America/New_York",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "VA": "America/New_York",
    "VT": "America/New_York",
    "WV": "America/New_York",
}


def _get_timezone_for_state(state: Optional[str]):
    if not state:
        return PACIFIC_TZ
    tz_name = STATE_TZ_MAP.get(state.upper(), "America/Los_Angeles")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _format_date_time(dt: Optional[datetime]) -> Dict[str, Optional[str]]:
    if not dt:
        return {"iso": None}
    return {"iso": dt.isoformat()}


def _convert_local_to_pacific(dt: Optional[datetime], state: Optional[str]) -> Dict[str, Optional[str]]:
    if not dt:
        return {
            "date": None,
            "time": None,
            "iso": None,
        }
    local_tz = _get_timezone_for_state(state)
    local_dt = dt.replace(tzinfo=local_tz)
    pacific_dt = local_dt.astimezone(PACIFIC_TZ)
    return _format_date_time(pacific_dt)


def _localize_to_state(dt: Optional[datetime], state: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    local_tz = _get_timezone_for_state(state)
    return dt.replace(tzinfo=local_tz)


def _map_equipment_code(equipment_elem: Optional[ET.Element]) -> Optional[str]:
    if equipment_elem is None:
        return None
    equipment_tags = [child.tag.lower() for child in equipment_elem]
    if not equipment_tags:
        return None
    van_tags = {"v", "r"}
    flatbed_tags = {"f", "sd", "lb", "hb", "dt", "dd", "po", "ac", "t"}
    if any(tag in flatbed_tags for tag in equipment_tags):
        return "F"
    if any(tag in van_tags for tag in equipment_tags):
        return "V"
    return None


def parse_date_element(date_elem) -> Optional[datetime]:
    """Parse date element from XML."""
    if date_elem is None:
        return None
    
    year = date_elem.find('year')
    month = date_elem.find('month')
    day = date_elem.find('day')
    hour = date_elem.find('hour')
    minute = date_elem.find('minute')
    
    if year is None or month is None or day is None:
        return None
    
    try:
        year_val = int(year.text) if year.text else None
        month_val = int(month.text) if month.text else None
        day_val = int(day.text) if day.text else None
        hour_val = int(hour.text) if hour and hour.text else 0
        minute_val = int(minute.text) if minute and minute.text else 0
        
        if year_val and month_val and day_val:
            return datetime(year_val, month_val, day_val, hour_val, minute_val)
    except (ValueError, TypeError):
        pass
    
    return None


def parse_load_xml(load_elem) -> Dict[str, Any]:
    """Parse a single load element from XML."""
    load_data = {}
    
    # Tracking number / load id
    tracking_number = load_elem.find('tracking-number')
    load_id_elem = load_elem.find('load-id')
    tracking_value = None
    if tracking_number is not None:
        tracking_attr = (
            tracking_number.get("id")
            or tracking_number.get("tracking-id")
            or tracking_number.get("external-id")
        )
        if tracking_attr and tracking_attr.strip():
            tracking_value = tracking_attr.strip()
        elif tracking_number.text and tracking_number.text.strip():
            tracking_value = tracking_number.text.strip()
    load_id_value = load_id_elem.text.strip() if load_id_elem is not None and load_id_elem.text and load_id_elem.text.strip() else None
    load_data['tracking_number'] = tracking_value
    load_data['load_id'] = load_id_value or tracking_value
    
    # Origin
    origin = load_elem.find('origin')
    if origin is not None:
        load_data['origin_city'] = origin.find('city').text if origin.find('city') is not None else None
        load_data['origin_state'] = origin.find('state').text if origin.find('state') is not None else None
        load_data['origin_postcode'] = origin.find('postcode').text if origin.find('postcode') is not None else None
        load_data['origin_county'] = origin.find('county').text if origin.find('county') is not None else None
        load_data['origin_country'] = origin.find('country').text if origin.find('country') is not None else None
        load_data['origin_latitude'] = float(origin.find('latitude').text) if origin.find('latitude') is not None and origin.find('latitude').text and origin.find('latitude').text != '0' else None
        load_data['origin_longitude'] = float(origin.find('longitude').text) if origin.find('longitude') is not None and origin.find('longitude').text and origin.find('longitude').text != '0' else None
        
        origin_date_start = origin.find('date-start')
        origin_pickup_dt = parse_date_element(origin_date_start)
        origin_state = load_data.get('origin_state')
        origin_pickup_local_dt = _localize_to_state(origin_pickup_dt, origin_state)
        load_data['origin_pickup_date'] = origin_pickup_local_dt
        
        origin_date_end = origin.find('date-end')
        origin_pickup_end_dt = parse_date_element(origin_date_end)
        origin_pickup_local_end_dt = _localize_to_state(origin_pickup_end_dt, origin_state)
        load_data['origin_pickup_date_end'] = origin_pickup_local_end_dt

        origin_local = _format_date_time(origin_pickup_local_dt)
        origin_local_end = _format_date_time(origin_pickup_local_end_dt)
        origin_pacific = _convert_local_to_pacific(origin_pickup_dt, origin_state)
        origin_pacific_end = _convert_local_to_pacific(origin_pickup_end_dt, origin_state)
        load_data['origin_pickup_local'] = origin_local["iso"]
        load_data['origin_pickup_local_end'] = origin_local_end["iso"]
        load_data['origin_pickup_pst'] = origin_pacific["iso"]
        load_data['origin_pickup_pst_end'] = origin_pacific_end["iso"]
    
    # Destination
    destination = load_elem.find('destination')
    if destination is not None:
        load_data['destination_city'] = destination.find('city').text if destination.find('city') is not None else None
        load_data['destination_state'] = destination.find('state').text if destination.find('state') is not None else None
        load_data['destination_postcode'] = destination.find('postcode').text if destination.find('postcode') is not None else None
        load_data['destination_county'] = destination.find('county').text if destination.find('county') is not None else None
        load_data['destination_country'] = destination.find('country').text if destination.find('country') is not None else None
        load_data['destination_latitude'] = float(destination.find('latitude').text) if destination.find('latitude') is not None and destination.find('latitude').text and destination.find('latitude').text != '0' else None
        load_data['destination_longitude'] = float(destination.find('longitude').text) if destination.find('longitude') is not None and destination.find('longitude').text and destination.find('longitude').text != '0' else None
        
        dest_date_start = destination.find('date-start')
        dest_delivery_dt = parse_date_element(dest_date_start)
        destination_state = load_data.get('destination_state')
        dest_delivery_local_dt = _localize_to_state(dest_delivery_dt, destination_state)
        load_data['destination_delivery_date'] = dest_delivery_local_dt
        
        dest_date_end = destination.find('date-end')
        dest_delivery_end_dt = parse_date_element(dest_date_end)
        dest_delivery_local_end_dt = _localize_to_state(dest_delivery_end_dt, destination_state)
        load_data['destination_delivery_date_end'] = dest_delivery_local_end_dt

        dest_local = _format_date_time(dest_delivery_local_dt)
        dest_local_end = _format_date_time(dest_delivery_local_end_dt)
        dest_pacific = _convert_local_to_pacific(dest_delivery_dt, destination_state)
        dest_pacific_end = _convert_local_to_pacific(dest_delivery_end_dt, destination_state)
        load_data['destination_delivery_local'] = dest_local["iso"]
        load_data['destination_delivery_local_end'] = dest_local_end["iso"]
        load_data['destination_delivery_pst'] = dest_pacific["iso"]
        load_data['destination_delivery_pst_end'] = dest_pacific_end["iso"]
    
    # Equipment
    equipment = load_elem.find('equipment')
    if equipment is not None:
        load_data['equipment'] = _map_equipment_code(equipment)
    
    # Load size
    loadsize = load_elem.find('loadsize')
    if loadsize is not None:
        load_data['full_load'] = loadsize.get('fullload', 'false').lower() == 'true'
        length = loadsize.find('length')
        width = loadsize.find('width')
        height = loadsize.find('height')
        weight = loadsize.find('weight')
        load_data['length'] = float(length.text) if length is not None and length.text else None
        load_data['width'] = float(width.text) if width is not None and width.text else None
        load_data['height'] = float(height.text) if height is not None and height.text else None
        load_data['weight'] = float(weight.text) if weight is not None and weight.text else None
    
    # Other fields
    load_count = load_elem.find('load-count')
    stops = load_elem.find('stops')
    distance = load_elem.find('distance')
    rate = load_elem.find('rate')
    comment = load_elem.find('comment')
    
    load_data['load_count'] = int(load_count.text) if load_count is not None and load_count.text else 1
    load_data['stops'] = int(stops.text) if stops is not None and stops.text else 0
    load_data['distance'] = float(distance.text) if distance is not None and distance.text else None
    load_data['rate'] = rate.text if rate is not None and rate.text else None
    load_data['comment'] = comment.text if comment is not None else None
    
    return load_data


def parse_posting_account(account_elem) -> Dict[str, Any]:
    """Parse posting account information from XML."""
    account_data = {}
    
    fields = ['UserName', 'Password', 'ContactName', 'ContactPhone', 'ContactFax', 
              'ContactEmail', 'CompanyName', 'UserID', 'mcNumber', 'dotNumber']
    
    for field in fields:
        elem = account_elem.find(field)
        account_data[field.lower()] = elem.text if elem is not None and elem.text else None
    
    return account_data


def parse_lbn_xml(xml_content: str) -> Dict[str, Any]:
    """Parse LoadBoard Network XML request."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML format: {str(e)}")
    
    if root.tag != 'LBNLoadPostings':
        raise ValueError(f"Invalid root element: {root.tag}. Expected 'LBNLoadPostings'")
    
    # Parse posting account
    posting_account = root.find('PostingAccount')
    if posting_account is None:
        raise ValueError("Missing PostingAccount element")
    
    account_data = parse_posting_account(posting_account)
    
    # Check for PostLoads or RemoveLoads
    post_loads_elem = root.find('PostLoads')
    remove_loads_elem = root.find('RemoveLoads')
    
    result = {
        'account': account_data,
        'operation': None,
        'loads': []
    }
    
    if post_loads_elem is not None:
        result['operation'] = 'post'
        loads = post_loads_elem.findall('load')
        for load_elem in loads:
            load_data = parse_load_xml(load_elem)
            result['loads'].append(load_data)
    elif remove_loads_elem is not None:
        result['operation'] = 'remove'
        loads = remove_loads_elem.findall('load')
        for load_elem in loads:
            load_data = parse_load_xml(load_elem)
            result['loads'].append(load_data)
    else:
        raise ValueError("Neither PostLoads nor RemoveLoads found")
    
    return result

