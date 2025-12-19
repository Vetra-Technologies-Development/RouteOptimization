"""
Find all possible route chains from Boston to Dallas based on search criteria.
Routes are chains of loads where delivery of one load is near pickup of next.
"""

import json
import math
from datetime import datetime
from typing import List, Dict, Tuple
from collections import defaultdict

# Maximum distance (in miles) between delivery and next pickup to consider them chainable
MAX_DEADHEAD_MILES = 100


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


def format_minutes_to_date(minutes: int) -> str:
    """Convert minutes to readable date."""
    ref_dt = datetime(2025, 11, 20, 0, 0, 0)
    dt = ref_dt + timedelta(minutes=minutes)
    return dt.strftime('%Y-%m-%d %H:%M')


def can_chain_loads(load1: Dict, load2: Dict, max_deadhead: float = MAX_DEADHEAD_MILES) -> Tuple[bool, float]:
    """
    Check if load2 can be chained after load1.
    Returns (can_chain, deadhead_miles)
    """
    # Delivery location of load1
    deliv1 = load1['destination']
    # Pickup location of load2
    pickup2 = load2['origin']
    
    # Calculate deadhead distance
    deadhead = haversine_distance(
        deliv1['latitude'], deliv1['longitude'],
        pickup2['latitude'], pickup2['longitude']
    )
    
    if deadhead > max_deadhead:
        return False, deadhead
    
    # Check time windows - delivery of load1 must allow time to reach pickup of load2
    load1_delivery_earliest = parse_iso_to_minutes(load1['delivery_window']['earliest'])
    load1_delivery_latest = parse_iso_to_minutes(load1['delivery_window']['latest'])
    load2_pickup_earliest = parse_iso_to_minutes(load2['pickup_window']['earliest'])
    load2_pickup_latest = parse_iso_to_minutes(load2['pickup_window']['latest'])
    
    # Add travel time for deadhead (estimate 1 hour per 50 miles, minimum 30 min)
    deadhead_time = max(30, int((deadhead / 50) * 60))
    
    # More lenient chaining: 
    # - Delivery can finish as late as pickup_latest allows (with deadhead time)
    # - We allow waiting at delivery location if needed
    # - Key constraint: delivery_latest + deadhead_time <= pickup_latest (with some buffer)
    
    # Allow up to 5 days buffer for flexibility (more lenient to find more chains)
    buffer_time = 1440 * 5  # 5 days in minutes
    
    # More lenient: Check if delivery can finish before pickup window closes (with large buffer)
    # This allows for waiting time and flexibility
    if load1_delivery_latest + deadhead_time > load2_pickup_latest + buffer_time:
        return False, deadhead
    
    # Even more lenient: as long as there's some overlap possibility
    # If delivery earliest + deadhead is way past pickup latest + buffer, it's not feasible
    if load1_delivery_earliest + deadhead_time > load2_pickup_latest + buffer_time + 1440:  # Extra day
        return False, deadhead
    
    return True, deadhead


def find_routes_from_origin(extracted_data: Dict, origin_city: str, origin_state: str, 
                            dest_city: str, dest_state: str, max_chain_length: int = 5, 
                            max_deadhead: float = MAX_DEADHEAD_MILES) -> List[Dict]:
    """
    Find all possible route chains from origin to destination.
    """
    nodes = extracted_data['nodes']
    loads = extracted_data['loads']
    search_criteria = extracted_data['search_criteria']
    
    # Find origin and destination nodes
    origin_node = None
    dest_node = None
    
    for node in nodes:
        if node['city'].lower() == origin_city.lower() and node['state'] == origin_state:
            if node.get('is_depot') or not origin_node:
                origin_node = node
        if node['city'].lower() == dest_city.lower() and node['state'] == dest_state:
            dest_node = node
    
    if not origin_node:
        print(f"Warning: Could not find origin node for {origin_city}, {origin_state}")
        origin_node = nodes[0]  # Use depot
    
    if not dest_node:
        print(f"Warning: Could not find destination node for {dest_city}, {dest_state}")
    
    # Find loads that start near origin
    origin_lat = origin_node['latitude']
    origin_lon = origin_node['longitude']
    
    starting_loads = []
    for load in loads:
        pickup_lat = load['origin']['latitude']
        pickup_lon = load['origin']['longitude']
        distance = haversine_distance(origin_lat, origin_lon, pickup_lat, pickup_lon)
        if distance <= max_deadhead:
            starting_loads.append((load, distance))
    
    # Sort by distance
    starting_loads.sort(key=lambda x: x[1])
    
    print(f"Found {len(starting_loads)} loads starting near {origin_city}, {origin_state}")
    print(f"Using max deadhead distance: {max_deadhead} miles")
    
    # Build chain graph - which loads can follow which
    chain_graph = defaultdict(list)
    for i, load1 in enumerate(loads):
        for j, load2 in enumerate(loads):
            if i != j:
                can_chain, deadhead = can_chain_loads(load1, load2, max_deadhead)
                if can_chain:
                    chain_graph[load1['load_id']].append((load2, deadhead))
    
    print(f"Built chain graph with {len(chain_graph)} load connections")
    print(f"Total possible chains: {sum(len(v) for v in chain_graph.values())}")
    
    # Find all routes using DFS
    all_routes = []
    
    def dfs_route(current_chain: List[Tuple[Dict, float]], current_load: Dict, depth: int):
        """Depth-first search to find all route chains."""
        if depth > max_chain_length:
            return
        
        # Check if current chain ends near destination
        if dest_node:
            final_deliv = current_load['destination']
            distance_to_dest = haversine_distance(
                final_deliv['latitude'], final_deliv['longitude'],
                dest_node['latitude'], dest_node['longitude']
            )
            
            if distance_to_dest <= max_deadhead:
                # This is a valid route
                route = {
                    'route_id': len(all_routes) + 1,
                    'segments': [],
                    'total_distance': 0,
                    'total_revenue': 0,
                    'total_deadhead': 0,
                    'ends_near_destination': True,
                    'final_distance_to_dest': distance_to_dest
                }
                
                for load, deadhead in current_chain:
                    route['segments'].append({
                        'load_id': load['load_id'],
                        'origin': f"{load['origin']['city']}, {load['origin']['state']}",
                        'destination': f"{load['destination']['city']}, {load['destination']['state']}",
                        'distance_miles': load['distance_miles'],
                        'revenue': load['revenue']['amount'],
                        'rate_per_mile': load['revenue']['rate_per_mile'],
                        'pickup_window': load['pickup_window'],
                        'delivery_window': load['delivery_window'],
                        'weight_pounds': load['weight_pounds'],
                        'deadhead_before': deadhead
                    })
                    route['total_distance'] += load['distance_miles']
                    route['total_revenue'] += load['revenue']['amount']
                    route['total_deadhead'] += deadhead
                
                # Check for duplicates
                chain_sig = tuple(l[0]['load_id'] for l in current_chain)
                if chain_sig not in processed_chains:
                    all_routes.append(route)
                    processed_chains.add(chain_sig)
        
        # Try to extend chain
        if current_load['load_id'] in chain_graph:
            for next_load, deadhead in chain_graph[current_load['load_id']]:
                # Avoid cycles
                if not any(l[0]['load_id'] == next_load['load_id'] for l in current_chain):
                    dfs_route(current_chain + [(next_load, deadhead)], next_load, depth + 1)
    
    # Start DFS from each starting load - check ALL starting loads
    print(f"\nFinding routes (max chain length: {max_chain_length})...")
    processed_chains = set()  # Track processed chains to avoid duplicates
    
    for start_load, start_deadhead in starting_loads:  # Check ALL starting loads, no limit
        chain_signature = (start_load['load_id'],)
        if chain_signature not in processed_chains:
            dfs_route([(start_load, start_deadhead)], start_load, 1)
            processed_chains.add(chain_signature)
    
    # Also add single-load routes that go directly to destination
    for load in loads:
        if dest_node:
            deliv = load['destination']
            distance_to_dest = haversine_distance(
                deliv['latitude'], deliv['longitude'],
                dest_node['latitude'], dest_node['longitude']
            )
            if distance_to_dest <= max_deadhead:
                pickup_lat = load['origin']['latitude']
                pickup_lon = load['origin']['longitude']
                start_distance = haversine_distance(origin_lat, origin_lon, pickup_lat, pickup_lon)
                if start_distance <= max_deadhead:
                    route = {
                        'route_id': len(all_routes) + 1,
                        'segments': [{
                            'load_id': load['load_id'],
                            'origin': f"{load['origin']['city']}, {load['origin']['state']}",
                            'destination': f"{load['destination']['city']}, {load['destination']['state']}",
                            'distance_miles': load['distance_miles'],
                            'revenue': load['revenue']['amount'],
                            'rate_per_mile': load['revenue']['rate_per_mile'],
                            'pickup_window': load['pickup_window'],
                            'delivery_window': load['delivery_window'],
                            'weight_pounds': load['weight_pounds'],
                            'deadhead_before': start_distance
                        }],
                        'total_distance': load['distance_miles'],
                        'total_revenue': load['revenue']['amount'],
                        'total_deadhead': start_distance,
                        'ends_near_destination': True,
                        'final_distance_to_dest': distance_to_dest
                    }
                    all_routes.append(route)
    
    # Remove duplicates based on segment sequence (origin->destination pairs)
    unique_routes = []
    seen_signatures = set()
    for route in all_routes:
        # Create signature based on origin->destination sequence, not load IDs
        sig = tuple((s['origin'], s['destination']) for s in route['segments'])
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_routes.append(route)
    
    # Sort routes by revenue (highest first), then by distance (shortest first)
    unique_routes.sort(key=lambda x: (-x['total_revenue'], x['total_distance']))
    
    # Renumber routes
    for i, route in enumerate(unique_routes):
        route['route_id'] = i + 1
    
    print(f"Found {len(unique_routes)} unique routes (removed {len(all_routes) - len(unique_routes)} duplicates)")
    
    # Print summary
    from collections import Counter
    seg_counts = Counter(len(r['segments']) for r in unique_routes)
    print("Routes by segment count:")
    for count, num in sorted(seg_counts.items()):
        print(f"  {count} segment(s): {num} route(s)")
    
    return unique_routes


def format_routes_output(routes: List[Dict], output_file: str = None):
    """Format routes in a readable format similar to sampleoutput.txt"""
    output = []
    output.append("________________")
    output.append("")
    output.append("")
    output.append("Chained Load Route Options (Multi-Stop)")
    
    if not routes:
        output.append("No routes found.")
        result = "\n".join(output)
        if output_file:
            with open(output_file, 'w') as f:
                f.write(result)
        return result
    
    for route in routes:
        option_num = route['route_id']
        num_segments = len(route['segments'])
        
        # Create descriptive title
        if num_segments == 1:
            seg = route['segments'][0]
            title = f"Option {option_num}: Direct Long-Haul ({seg['origin']} to {seg['destination']})"
            description = f"If flexibility on the exact date is possible, a direct load is available for this route."
        else:
            # Build route description
            origins = [s['origin'].split(',')[0] for s in route['segments']]
            dests = [s['destination'].split(',')[0] for s in route['segments']]
            route_str = " → ".join([f"{o}" for o in origins] + [dests[-1]])
            title = f"Option {option_num}: {num_segments}-Stop Chain ({route_str})"
            description = f"This chain connects {num_segments} loads together, with minimal deadhead miles between legs."
        
        output.append(title)
        output.append(description)
        output.append("Segment\tOrigin (State)\tDestination (State)\tPickup Window (2025)\tDelivery Window (2025)\tDistance (Miles)\tRevenue (USD)")
        
        for i, segment in enumerate(route['segments']):
            seg_num = i + 1
            origin = segment['origin']
            dest = segment['destination']
            
            # Format dates to match sample format (Nov 26th - Nov 27th style)
            pickup_earliest = segment['pickup_window']['earliest']
            pickup_latest = segment['pickup_window']['latest']
            delivery_earliest = segment['delivery_window']['earliest']
            delivery_latest = segment['delivery_window']['latest']
            
            # Parse and format dates
            try:
                from datetime import datetime
                if pickup_earliest.endswith('Z'):
                    pickup_earliest = pickup_earliest[:-1] + '+00:00'
                if pickup_latest.endswith('Z'):
                    pickup_latest = pickup_latest[:-1] + '+00:00'
                if delivery_earliest.endswith('Z'):
                    delivery_earliest = delivery_earliest[:-1] + '+00:00'
                if delivery_latest.endswith('Z'):
                    delivery_latest = delivery_latest[:-1] + '+00:00'
                
                pu_earliest_dt = datetime.fromisoformat(pickup_earliest)
                pu_latest_dt = datetime.fromisoformat(pickup_latest)
                del_earliest_dt = datetime.fromisoformat(delivery_earliest)
                del_latest_dt = datetime.fromisoformat(delivery_latest)
                
                pickup_str = f"{pu_earliest_dt.strftime('%b %d')} - {pu_latest_dt.strftime('%b %d')}"
                delivery_str = f"{del_earliest_dt.strftime('%b %d')} - {del_latest_dt.strftime('%b %d')}"
            except:
                pickup_str = f"{pickup_earliest[:10]} - {pickup_latest[:10]}"
                delivery_str = f"{delivery_earliest[:10]} - {delivery_latest[:10]}"
            
            revenue_str = f"${segment['revenue']:,.2f}" if segment['revenue'] > 0 else "Rate not posted"
            distance = segment['distance_miles']
            
            output.append(f"{seg_num}\t{origin}\t{dest}\t{pickup_str}\t{delivery_str}\t{distance:.0f}\t{revenue_str}")
        
        output.append("Chain Summary")
        output.append("")
        output.append("")
        output.append("")
        output.append(f"Total Distance: {route['total_distance']:,.0f} miles (approx.)")
        if route['total_revenue'] > 0:
            output.append(f"Total Revenue: ${route['total_revenue']:,.2f}")
        output.append("")
        output.append("")
    
    output.append("________________")
    result = "\n".join(output)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(result)
        print(f"✓ Routes saved to {output_file}")
    
    return result


def main():
    from datetime import timedelta
    
    print("Loading extracted data...")
    with open('extracted_data.json', 'r') as f:
        extracted_data = json.load(f)
    
    search_criteria = extracted_data['search_criteria']
    origin = search_criteria.get('origin', {})
    destination = search_criteria.get('destination', {})
    
    origin_city = origin.get('city', 'Boston')
    origin_state = origin.get('state', 'MA')
    dest_city = destination.get('city', 'Dallas')
    dest_state = destination.get('state', 'TX')
    
    print(f"\nFinding all possible routes from {origin_city}, {origin_state} to {dest_city}, {dest_state}")
    print("=" * 80)
    
    # Get max deadhead from search criteria
    max_deadhead = search_criteria.get('options', {}).get('maxOriginDeadheadMiles', 100)
    
    # Find all routes - no restrictions on number
    routes = find_routes_from_origin(
        extracted_data,
        origin_city,
        origin_state,
        dest_city,
        dest_state,
        max_chain_length=10,  # Allow longer chains (up to 10 loads)
        max_deadhead=max_deadhead
    )
    
    print(f"\nFound {len(routes)} possible routes")
    
    # Format and save output
    formatted_output = format_routes_output(routes, 'all_possible_routes.txt')
    
    # Also save as JSON
    with open('all_possible_routes.json', 'w') as f:
        json.dump({
            'search_criteria': search_criteria,
            'total_routes': len(routes),
            'routes': routes
        }, f, indent=2)
    print("✓ Routes saved to all_possible_routes.json")
    
    # Print first 5 routes
    print("\n" + "=" * 80)
    print("FIRST 5 ROUTES:")
    print("=" * 80)
    print(formatted_output[:5000])  # Print first 5000 characters
    
    if len(routes) > 5:
        print(f"\n... and {len(routes) - 5} more routes (see all_possible_routes.txt for full list)")


if __name__ == "__main__":
    main()

