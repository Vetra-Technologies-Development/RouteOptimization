"""XML parsing utilities for LoadBoard Network."""
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any, List


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
    
    # Tracking number
    tracking_number = load_elem.find('tracking-number')
    load_data['tracking_number'] = tracking_number.text if tracking_number is not None and tracking_number.text else None
    
    # Origin
    origin = load_elem.find('origin')
    if origin is not None:
        load_data['origin_city'] = origin.find('city').text if origin.find('city') is not None else None
        load_data['origin_state'] = origin.find('state').text if origin.find('state') is not None else None
        load_data['origin_postcode'] = origin.find('postcode').text if origin.find('postcode') is not None else None
        load_data['origin_latitude'] = float(origin.find('latitude').text) if origin.find('latitude') is not None and origin.find('latitude').text else None
        load_data['origin_longitude'] = float(origin.find('longitude').text) if origin.find('longitude') is not None and origin.find('longitude').text else None
        
        origin_date_start = origin.find('date-start')
        load_data['origin_pickup_date'] = parse_date_element(origin_date_start)
    
    # Destination
    destination = load_elem.find('destination')
    if destination is not None:
        load_data['destination_city'] = destination.find('city').text if destination.find('city') is not None else None
        load_data['destination_state'] = destination.find('state').text if destination.find('state') is not None else None
        load_data['destination_postcode'] = destination.find('postcode').text if destination.find('postcode') is not None else None
        load_data['destination_latitude'] = float(destination.find('latitude').text) if destination.find('latitude') is not None and destination.find('latitude').text else None
        load_data['destination_longitude'] = float(destination.find('longitude').text) if destination.find('longitude') is not None and destination.find('longitude').text else None
        
        dest_date_start = destination.find('date-start')
        load_data['destination_delivery_date'] = parse_date_element(dest_date_start)
    
    # Equipment
    equipment = load_elem.find('equipment')
    if equipment is not None:
        # Parse equipment types (can be multiple)
        equipment_types = []
        for child in equipment:
            eq_type = child.tag
            attrs = child.attrib
            equipment_types.append({'type': eq_type, 'attributes': attrs})
        load_data['equipment'] = equipment_types
    
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

