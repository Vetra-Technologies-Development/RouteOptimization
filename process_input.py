"""
Generalized script to process any JSON file with searchCriteria and loads structure.
Solves the VRPTW problem and finds all possible route options.

Usage:
    python3 process_boston_dallas.py [input_file.json] [max_loads]
    
Examples:
    python3 process_boston_dallas.py boston-dallas-20.json
    python3 process_boston_dallas.py boston-dallas-20.json 20  # Limit to first 20 loads
    python3 process_boston_dallas.py my_routes.json
"""

import json
import requests
import sys
from datetime import datetime
from typing import Dict, List, Tuple
import math

# API endpoint
API_URL = "http://localhost:8000/solve_routes"


def parse_iso_to_minutes(iso_string: str) -> int:
    """Convert ISO 8601 timestamp to minutes from reference time."""
    # Parse ISO format - handle Z timezone
    if iso_string.endswith('Z'):
        iso_string = iso_string[:-1] + '+00:00'
    
    try:
        dt = datetime.fromisoformat(iso_string)
    except ValueError:
        # Try parsing without timezone
        dt = datetime.fromisoformat(iso_string.replace('Z', ''))
    
    # Reference time in UTC
    ref_dt = datetime(2025, 11, 20, 0, 0, 0)
    
    # Calculate difference
    if dt.tzinfo:
        # Convert to naive datetime for comparison
        dt_naive = dt.replace(tzinfo=None)
        delta = dt_naive - ref_dt
    else:
        delta = dt - ref_dt
    
    return int(delta.total_seconds() / 60)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two lat/lon points."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def estimate_travel_time_miles(distance_miles: float) -> int:
    """Estimate travel time in minutes based on distance (assuming 50 mph average)."""
    return int((distance_miles / 50) * 60)


def process_loads_data(json_file: str, max_loads: int = None, max_deadhead_miles: int = None) -> dict:
    """Process the JSON file and convert it to API format."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    loads = data['loads']
    if max_loads:
        loads = loads[:max_loads]
        print(f"Processing only first {len(loads)} loads...")
    search_criteria = data['searchCriteria']
    
    # Extract depot location (origin from search criteria)
    origin_info = search_criteria.get('origin', {})
    if not origin_info:
        raise ValueError("searchCriteria must contain 'origin' with latitude and longitude")
    
    depot_lat = origin_info.get('latitude')
    depot_lon = origin_info.get('longitude')
    
    if depot_lat is None or depot_lon is None:
        raise ValueError("searchCriteria.origin must contain 'latitude' and 'longitude'")
    
    # Collect all unique locations
    locations = []
    location_to_index = {}
    
    # Add depot first (index 0)
    depot_key = (depot_lat, depot_lon)
    locations.append({
        'lat': depot_lat,
        'lon': depot_lon,
        'type': 'depot',
        'city': origin_info.get('city', 'Origin')
    })
    location_to_index[depot_key] = 0
    
    # Process all loads to collect unique locations
    pickup_delivery_pairs = []
    load_info = []
    load_id_map = {}  # Map (pickup_idx, delivery_idx) -> load data
    
    for load in loads:
        origin = load.get('origin', {})
        dest = load.get('destination', {})
        
        if not origin or not dest:
            continue
        
        origin_lat = origin.get('latitude')
        origin_lon = origin.get('longitude')
        dest_lat = dest.get('latitude')
        dest_lon = dest.get('longitude')
        
        if None in [origin_lat, origin_lon, dest_lat, dest_lon]:
            continue
        
        origin_key = (origin_lat, origin_lon)
        dest_key = (dest_lat, dest_lon)
        
        # Add origin if not seen
        if origin_key not in location_to_index:
            idx = len(locations)
            location_to_index[origin_key] = idx
            locations.append({
                'lat': origin['latitude'],
                'lon': origin['longitude'],
                'type': 'pickup',
                'city': origin.get('city', 'Unknown')
            })
        
        # Add destination if not seen
        if dest_key not in location_to_index:
            idx = len(locations)
            location_to_index[dest_key] = idx
            locations.append({
                'lat': dest['latitude'],
                'lon': dest['longitude'],
                'type': 'delivery',
                'city': dest.get('city', 'Unknown')
            })
        
        pickup_idx = location_to_index[origin_key]
        delivery_idx = location_to_index[dest_key]
        
        pickup_delivery_pairs.append([pickup_idx, delivery_idx])
        
        # Extract load data with safe defaults
        requirements = load.get('requirements', {})
        revenue = load.get('revenue', {})
        
        load_data = {
            'pickup_idx': pickup_idx,
            'delivery_idx': delivery_idx,
            'weight': requirements.get('weightPounds', 0),
            'pickup_window': load.get('pickupWindow', {}),
            'delivery_window': load.get('deliveryWindow', {}),
            'distance_miles': load.get('distanceMiles', 0),
            'estimated_duration': load.get('estimatedDurationMinutes', 0),
            'revenue': revenue.get('amount', 0),
            'origin': origin,
            'destination': dest,
            'load_id': load.get('id', '')
        }
        load_info.append(load_data)
        load_id_map[(pickup_idx, delivery_idx)] = load_data
    
    num_nodes = len(locations)
    
    # Build time matrix
    # For now, use estimated duration from loads for direct routes
    # For other routes, estimate based on distance
    time_matrix = []
    
    for i in range(num_nodes):
        row = []
        for j in range(num_nodes):
            if i == j:
                row.append(0)
            else:
                # Try to find a direct load between these locations
                direct_time = None
                for info in load_info:
                    if (info['pickup_idx'] == i and info['delivery_idx'] == j):
                        direct_time = info['estimated_duration']
                        break
                
                if direct_time:
                    row.append(direct_time)
                else:
                    # Estimate based on distance
                    loc1 = locations[i]
                    loc2 = locations[j]
                    distance = haversine_distance(
                        loc1['lat'], loc1['lon'],
                        loc2['lat'], loc2['lon']
                    )
                    estimated_time = estimate_travel_time_miles(distance)
                    row.append(estimated_time)
        
        time_matrix.append(row)
    
    # Build demands array (0 for depot, positive for pickup, negative for delivery)
    demands = [0] * num_nodes
    for info in load_info:
        demands[info['pickup_idx']] += info['weight']
        demands[info['delivery_idx']] -= info['weight']
    
    # Build time windows - use the widest possible window for each location
    # This makes the problem more feasible
    time_windows = []
    for i in range(num_nodes):
        if i == 0:  # Depot
            # Depot available from start to end of planning horizon
            time_windows.append([0, 1440 * 20])  # 20 days in minutes
        else:
            # Find all time windows for this location and use the union (widest range)
            all_earliest = []
            all_latest = []
            
            for info in load_info:
                pickup_window = info.get('pickup_window', {})
                delivery_window = info.get('delivery_window', {})
                
                if info['pickup_idx'] == i and pickup_window:
                    pickup_earliest_str = pickup_window.get('earliest')
                    pickup_latest_str = pickup_window.get('latest')
                    if pickup_earliest_str and pickup_latest_str:
                        pickup_earliest = parse_iso_to_minutes(pickup_earliest_str)
                        pickup_latest = parse_iso_to_minutes(pickup_latest_str)
                        all_earliest.append(pickup_earliest)
                        all_latest.append(pickup_latest)
                
                if info['delivery_idx'] == i and delivery_window:
                    delivery_earliest_str = delivery_window.get('earliest')
                    delivery_latest_str = delivery_window.get('latest')
                    if delivery_earliest_str and delivery_latest_str:
                        delivery_earliest = parse_iso_to_minutes(delivery_earliest_str)
                        delivery_latest = parse_iso_to_minutes(delivery_latest_str)
                        all_earliest.append(delivery_earliest)
                        all_latest.append(delivery_latest)
            
            if all_earliest and all_latest:
                earliest = min(all_earliest)
                latest = max(all_latest)
                # Add buffer to make more feasible
                earliest = max(0, earliest - 60)  # 1 hour buffer before
                latest = latest + 1440  # 1 day buffer after
            else:
                earliest = 0
                latest = 1440 * 20  # 20 days
            
            time_windows.append([earliest, latest])
    
    # Configuration - Single vehicle for multiple route options
    num_vehicles = 1  # Single truck as requested
    vehicle_capacity = 45000  # Max weight in pounds (typical truck capacity)
    max_route_time = 1440 * 20  # 20 days max route time in minutes (very flexible)
    
    return {
        'time_matrix': time_matrix,
        'pickups_deliveries': pickup_delivery_pairs,
        'demands': demands,
        'time_windows': time_windows,
        'num_vehicles': num_vehicles,
        'vehicle_capacity': vehicle_capacity,
        'max_route_time': max_route_time,
        'depot_index': 0,
        'locations': locations,  # For reference
        'load_info': load_info,  # Store load information for output formatting
        'load_id_map': load_id_map  # Map for quick lookup
    }


def format_route_as_chain(route_stops, load_id_map, locations):
    """Convert route stops into chain segments (pickup->delivery pairs)."""
    segments = []
    visited_pickups = set()
    
    # Track which loads have been picked up
    pickup_to_delivery = {}
    for (pickup_idx, delivery_idx), load_data in load_id_map.items():
        pickup_to_delivery[pickup_idx] = (delivery_idx, load_data)
    
    # Go through stops and identify segments
    for stop in route_stops:
        node_idx = stop['node_index']
        if node_idx in pickup_to_delivery:
            # This is a pickup
            delivery_idx, load_data = pickup_to_delivery[node_idx]
            if node_idx not in visited_pickups:
                visited_pickups.add(node_idx)
                # Find when delivery happens
                delivery_stop = None
                for s in route_stops:
                    if s['node_index'] == delivery_idx:
                        delivery_stop = s
                        break
                
                if delivery_stop:
                    origin = load_data['origin']
                    dest = load_data['destination']
                    segments.append({
                        'segment_num': len(segments) + 1,
                        'origin': f"{origin.get('city', 'Unknown')} ({origin.get('state', '')})",
                        'destination': f"{dest.get('city', 'Unknown')} ({dest.get('state', '')})",
                        'pickup_window': load_data['pickup_window'],
                        'delivery_window': load_data['delivery_window'],
                        'distance_miles': load_data['distance_miles'],
                        'revenue': load_data['revenue'],
                        'pickup_time': stop['arrival_time_minutes'],
                        'delivery_time': delivery_stop['arrival_time_minutes']
                    })
    
    return segments


def format_output_like_sample(result, api_input):
    """Format the solution output to match sampleoutput.txt style."""
    output = []
    output.append("________________\n")
    output.append("\n")
    output.append("Chained Load Route Options (Multi-Stop)\n")
    
    if 'route_options' in result and len(result['route_options']) > 0:
        options = result['route_options']
    elif result.get('routes') and len(result['routes']) > 0:
        # Convert routes to options format
        options = []
        for i, route in enumerate(result['routes']):
            options.append({
                'option_id': i + 1,
                'stops': route['stops'],
                'total_route_time_minutes': route['total_route_time_minutes']
            })
    else:
        return "No route options found.\n"
    
    for option in options:
        option_id = option.get('option_id', 1)
        stops = option.get('stops', [])
        
        # Convert stops to chain segments
        segments = format_route_as_chain(stops, api_input.get('load_id_map', {}), api_input.get('locations', []))
        
        if not segments:
            continue
        
        output.append(f"Option {option_id}: Route with {len(segments)} Segment(s)\n")
        output.append(f"This route chains {len(segments)} loads together.\n")
        output.append("Segment\tOrigin (State)\tDestination (State)\tPickup Window (2025)\tDelivery Window (2025)\tDistance (Miles)\tRevenue (USD)\n")
        
        total_distance = 0
        total_revenue = 0
        
        for seg in segments:
            # Format dates
            pickup_earliest = seg['pickup_window']['earliest'][:10]
            pickup_latest = seg['pickup_window']['latest'][:10]
            delivery_earliest = seg['delivery_window']['earliest'][:10]
            delivery_latest = seg['delivery_window']['latest'][:10]
            
            revenue_str = f"${seg['revenue']:,.2f}" if seg['revenue'] > 0 else "Rate not posted"
            
            output.append(f"{seg['segment_num']}\t{seg['origin']}\t{seg['destination']}\t"
                         f"{pickup_earliest} - {pickup_latest}\t{delivery_earliest} - {delivery_latest}\t"
                         f"{seg['distance_miles']}\t{revenue_str}\n")
            
            total_distance += seg['distance_miles']
            total_revenue += seg['revenue']
        
        output.append("Chain Summary\n")
        output.append("\n")
        output.append("\n")
        output.append("\n")
        output.append(f"Total Distance: {total_distance:,.0f} miles (approx.)\n")
        if total_revenue > 0:
            output.append(f"Total Revenue: ${total_revenue:,.2f}\n")
        output.append("\n")
        output.append("\n")
    
    output.append("________________\n")
    return "".join(output)


def main():
    # Parse command line arguments
    input_file = 'boston-dallas-20.json'  # Default
    max_loads = None
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            max_loads = int(sys.argv[2])
            print(f"Limiting to first {max_loads} loads for testing...")
        except ValueError:
            print(f"Warning: '{sys.argv[2]}' is not a valid number. Processing all loads.")
    
    print(f"Processing {input_file}...")
    print("=" * 60)
    
    try:
        # Process the JSON file
        api_input = process_loads_data(input_file, max_loads=max_loads)
        
        print(f"Number of nodes: {len(api_input['time_matrix'])}")
        print(f"Number of loads: {len(api_input['pickups_deliveries'])}")
        print(f"Number of vehicles: {api_input['num_vehicles']}")
        print(f"Vehicle capacity: {api_input['vehicle_capacity']} lbs")
        print(f"Max route time: {api_input['max_route_time']} minutes ({api_input['max_route_time'] / 1440:.1f} days)")
        print()
        
        # Validate time windows
        print("Validating time windows...")
        invalid_windows = []
        for i, tw in enumerate(api_input['time_windows']):
            if tw[0] > tw[1]:
                invalid_windows.append(i)
        if invalid_windows:
            print(f"Warning: Found {len(invalid_windows)} invalid time windows (earliest > latest)")
            print(f"Fixing them...")
            for i in invalid_windows:
                api_input['time_windows'][i] = [api_input['time_windows'][i][1], api_input['time_windows'][i][0]]
        
        # Prepare API request (remove locations and load info from the request)
        request_data = {k: v for k, v in api_input.items() if k not in ['locations', 'load_info', 'load_id_map']}
        
        print("Sending request to VRPTW Solver API...")
        print(f"URL: {API_URL}\n")
        
        response = requests.post(API_URL, json=request_data, timeout=300)  # 5 minutes timeout
        response.raise_for_status()
        
        result = response.json()
        
        print("=" * 60)
        print("SOLUTION RESULT")
        print("=" * 60)
        print(f"Solution Found: {result['solution_found']}")
        print(f"Message: {result['message']}\n")
        
        if result['solution_found']:
            # Display multiple route options if available
            if 'route_options' in result and len(result['route_options']) > 0:
                print(f"Found {result.get('num_options_found', len(result['route_options']))} Route Options:\n")
                
                for option in result['route_options']:
                    print(f"{'='*60}")
                    print(f"Route Option {option.get('option_id', 'N/A')}: {option.get('description', '')}")
                    print(f"{'='*60}")
                    print(f"Total Route Time: {option['total_route_time_minutes']} minutes ({option['total_route_time_minutes'] / 60:.1f} hours)")
                    print(f"Number of Stops: {len(option['stops'])}")
                    print("Stops:")
                    for stop in option['stops']:
                        node_idx = stop['node_index']
                        loc = api_input['locations'][node_idx]
                        city = loc.get('city', 'Unknown')
                        arrival_hours = stop['arrival_time_minutes'] / 60
                        print(f"  - Node {node_idx} ({city}): "
                              f"Arrival at {stop['arrival_time_minutes']} min ({arrival_hours:.1f} hours), "
                              f"Load: {stop['load_on_vehicle']} lbs")
                    print()
            else:
                # Fallback to regular routes display
                print(f"Number of Routes: {len(result['routes'])}\n")
                for route in result['routes']:
                    print(f"Route for Vehicle {route['vehicle_id']}:")
                    print(f"  Total Route Time: {route['total_route_time_minutes']} minutes ({route['total_route_time_minutes'] / 60:.1f} hours)")
                    print(f"  Number of Stops: {len(route['stops'])}")
                    print("  Stops:")
                    for stop in route['stops']:
                        node_idx = stop['node_index']
                        loc = api_input['locations'][node_idx]
                        city = loc.get('city', 'Unknown')
                        arrival_hours = stop['arrival_time_minutes'] / 60
                        print(f"    - Node {node_idx} ({city}): "
                              f"Arrival at {stop['arrival_time_minutes']} min ({arrival_hours:.1f} hours), "
                              f"Load: {stop['load_on_vehicle']} lbs")
                    print()
        else:
            print("No feasible solution was found for the given constraints.")
            print("Try adjusting:")
            print("  - Number of vehicles")
            print("  - Vehicle capacity")
            print("  - Maximum route time")
        
        print("=" * 60)
        
        # Format and save output like sampleoutput.txt
        formatted_output = format_output_like_sample(result, api_input)
        with open('solution_output.txt', 'w') as f:
            f.write(formatted_output)
        print("\nFormatted output saved to solution_output.txt")
        
        # Also save JSON
        with open('solution_output.json', 'w') as f:
            json.dump(result, f, indent=2)
        print("JSON output saved to solution_output.json")
        
        # Print formatted output
        print("\n" + "=" * 60)
        print("FORMATTED OUTPUT (like sampleoutput.txt):")
        print("=" * 60)
        print(formatted_output)
        
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}")
        print(f"Usage: python3 process_boston_dallas.py [input_file.json] [max_loads]")
    except ValueError as e:
        print(f"Error: Invalid JSON structure - {e}")
        print(f"Expected JSON structure:")
        print(f"  {{")
        print(f"    'searchCriteria': {{ 'origin': {{ 'latitude': ..., 'longitude': ... }}, ... }},")
        print(f"    'loads': [ {{ 'origin': ..., 'destination': ..., 'pickupWindow': ..., ... }} ]")
        print(f"  }}")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API.")
        print("Make sure the FastAPI server is running:")
        print("  uvicorn main:app --reload")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

