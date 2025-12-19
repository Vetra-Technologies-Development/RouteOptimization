"""
Extract data from boston-dallas-20.json:
- searchCriteria
- All nodes (origin, destination)
- loadid
- availability (pickup/delivery windows)
- rate (revenue)
- miles (distance)
"""

import json
from datetime import datetime
from typing import List, Dict

def parse_iso_date(iso_string: str) -> str:
    """Convert ISO 8601 timestamp to readable date format."""
    try:
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_string


def extract_all_data(json_file: str) -> Dict:
    """Extract all required data from the JSON file."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Extract searchCriteria
    search_criteria = data.get('searchCriteria', {})
    
    # Extract all loads
    loads = data.get('loads', [])
    
    # Extract nodes and load information
    nodes = []
    load_data = []
    
    # Add depot node from searchCriteria
    origin = search_criteria.get('origin', {})
    depot_node = {
        'node_id': 0,
        'type': 'depot',
        'city': origin.get('city', ''),
        'state': origin.get('state', ''),
        'latitude': origin.get('latitude', 0),
        'longitude': origin.get('longitude', 0),
        'is_depot': True
    }
    nodes.append(depot_node)
    
    # Track unique locations
    location_to_node_id = {}
    node_id_counter = 1
    
    # Process each load
    for load in loads:
        load_id = load.get('id', '')
        origin = load.get('origin', {})
        destination = load.get('destination', {})
        revenue = load.get('revenue', {})
        pickup_window = load.get('pickupWindow', {})
        delivery_window = load.get('deliveryWindow', {})
        
        # Get origin node ID
        origin_key = (origin.get('latitude'), origin.get('longitude'))
        if origin_key not in location_to_node_id:
            origin_node = {
                'node_id': node_id_counter,
                'type': 'pickup',
                'city': origin.get('city', ''),
                'state': origin.get('state', ''),
                'latitude': origin.get('latitude', 0),
                'longitude': origin.get('longitude', 0),
                'is_depot': False
            }
            nodes.append(origin_node)
            location_to_node_id[origin_key] = node_id_counter
            node_id_counter += 1
        origin_node_id = location_to_node_id[origin_key]
        
        # Get destination node ID
        dest_key = (destination.get('latitude'), destination.get('longitude'))
        if dest_key not in location_to_node_id:
            dest_node = {
                'node_id': node_id_counter,
                'type': 'delivery',
                'city': destination.get('city', ''),
                'state': destination.get('state', ''),
                'latitude': destination.get('latitude', 0),
                'longitude': destination.get('longitude', 0),
                'is_depot': False
            }
            nodes.append(dest_node)
            location_to_node_id[dest_key] = node_id_counter
            node_id_counter += 1
        dest_node_id = location_to_node_id[dest_key]
        
        # Extract load information
        load_info = {
            'load_id': load_id,
            'origin_node_id': origin_node_id,
            'destination_node_id': dest_node_id,
            'origin': {
                'city': origin.get('city', ''),
                'state': origin.get('state', ''),
                'latitude': origin.get('latitude', 0),
                'longitude': origin.get('longitude', 0)
            },
            'destination': {
                'city': destination.get('city', ''),
                'state': destination.get('state', ''),
                'latitude': destination.get('latitude', 0),
                'longitude': destination.get('longitude', 0)
            },
            'pickup_window': {
                'earliest': pickup_window.get('earliest', ''),
                'latest': pickup_window.get('latest', ''),
                'earliest_parsed': parse_iso_date(pickup_window.get('earliest', '')),
                'latest_parsed': parse_iso_date(pickup_window.get('latest', ''))
            },
            'delivery_window': {
                'earliest': delivery_window.get('earliest', ''),
                'latest': delivery_window.get('latest', ''),
                'earliest_parsed': parse_iso_date(delivery_window.get('earliest', '')),
                'latest_parsed': parse_iso_date(delivery_window.get('latest', ''))
            },
            'distance_miles': load.get('distanceMiles', 0),
            'revenue': {
                'amount': revenue.get('amount', 0),
                'currency': revenue.get('currency', 'USD'),
                'rate_per_mile': revenue.get('ratePerMile', 0)
            },
            'estimated_duration_minutes': load.get('estimatedDurationMinutes', 0),
            'weight_pounds': load.get('requirements', {}).get('weightPounds', 0)
        }
        load_data.append(load_info)
    
    return {
        'search_criteria': search_criteria,
        'nodes': nodes,
        'loads': load_data,
        'summary': {
            'total_nodes': len(nodes),
            'total_loads': len(load_data),
            'depot': {
                'city': origin.get('city', ''),
                'state': origin.get('state', ''),
                'latitude': origin.get('latitude', 0),
                'longitude': origin.get('longitude', 0)
            }
        }
    }


def print_extracted_data(data: Dict):
    """Print the extracted data in a readable format."""
    print("=" * 80)
    print("EXTRACTED DATA FROM boston-dallas-20.json")
    print("=" * 80)
    
    # Print searchCriteria
    print("\n1. SEARCH CRITERIA:")
    print("-" * 80)
    search = data['search_criteria']
    print(f"Origin: {search.get('origin', {}).get('city', '')}, {search.get('origin', {}).get('state', '')}")
    print(f"  Latitude: {search.get('origin', {}).get('latitude', 0)}")
    print(f"  Longitude: {search.get('origin', {}).get('longitude', 0)}")
    print(f"Destination: {search.get('destination', {}).get('city', '')}, {search.get('destination', {}).get('state', '')}")
    print(f"  Latitude: {search.get('destination', {}).get('latitude', 0)}")
    print(f"  Longitude: {search.get('destination', {}).get('longitude', 0)}")
    print(f"Equipment: {', '.join(search.get('equipment', []))}")
    availability = search.get('availability', {})
    print(f"Availability: {availability.get('earliest', '')} to {availability.get('latest', '')}")
    
    # Print summary
    print("\n2. SUMMARY:")
    print("-" * 80)
    summary = data['summary']
    print(f"Total Nodes: {summary['total_nodes']}")
    print(f"Total Loads: {summary['total_loads']}")
    print(f"Depot: {summary['depot']['city']}, {summary['depot']['state']}")
    
    # Print nodes
    print("\n3. ALL NODES:")
    print("-" * 80)
    print(f"{'Node ID':<10} {'Type':<12} {'City':<25} {'State':<8} {'Latitude':<12} {'Longitude':<12}")
    print("-" * 80)
    for node in data['nodes']:
        print(f"{node['node_id']:<10} {node['type']:<12} {node['city']:<25} {node['state']:<8} "
              f"{node['latitude']:<12.6f} {node['longitude']:<12.6f}")
    
    # Print loads
    print("\n4. ALL LOADS:")
    print("-" * 80)
    print(f"{'Load ID':<25} {'Origin':<30} {'Destination':<30} {'Miles':<8} {'Rate':<12} {'Revenue':<12}")
    print("-" * 80)
    for load in data['loads'][:20]:  # Show first 20 loads
        origin_str = f"{load['origin']['city']}, {load['origin']['state']}"
        dest_str = f"{load['destination']['city']}, {load['destination']['state']}"
        revenue = load['revenue']['amount']
        rate = load['revenue']['rate_per_mile']
        miles = load['distance_miles']
        print(f"{load['load_id']:<25} {origin_str:<30} {dest_str:<30} {miles:<8.0f} "
              f"${rate:<11.2f} ${revenue:<11.2f}")
    
    if len(data['loads']) > 20:
        print(f"\n... and {len(data['loads']) - 20} more loads")
    
    # Print detailed load information (first 5)
    print("\n5. DETAILED LOAD INFORMATION (First 5):")
    print("-" * 80)
    for i, load in enumerate(data['loads'][:5]):
        print(f"\nLoad {i+1}: {load['load_id']}")
        print(f"  Origin Node ID: {load['origin_node_id']} - {load['origin']['city']}, {load['origin']['state']}")
        print(f"  Destination Node ID: {load['destination_node_id']} - {load['destination']['city']}, {load['destination']['state']}")
        print(f"  Distance: {load['distance_miles']} miles")
        print(f"  Revenue: ${load['revenue']['amount']:.2f} (Rate: ${load['revenue']['rate_per_mile']:.2f}/mile)")
        print(f"  Weight: {load['weight_pounds']} lbs")
        print(f"  Duration: {load['estimated_duration_minutes']} minutes ({load['estimated_duration_minutes']/60:.1f} hours)")
        print(f"  Pickup Window: {load['pickup_window']['earliest_parsed']} to {load['pickup_window']['latest_parsed']}")
        print(f"  Delivery Window: {load['delivery_window']['earliest_parsed']} to {load['delivery_window']['latest_parsed']}")


def save_to_json(data: Dict, output_file: str):
    """Save extracted data to JSON file."""
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Extracted data saved to {output_file}")


def main():
    print("Extracting data from boston-dallas-20.json...")
    print()
    
    try:
        # Extract data
        extracted_data = extract_all_data('boston-dallas-20.json')
        
        # Print to console
        print_extracted_data(extracted_data)
        
        # Save to JSON
        save_to_json(extracted_data, 'extracted_data.json')
        
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        
    except FileNotFoundError:
        print("Error: Could not find boston-dallas-20.json")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

