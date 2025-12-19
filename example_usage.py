"""
Example script demonstrating how to use the VRPTW Solver API.

This example creates a simple routing problem with:
- 1 depot (node 0)
- 1 pickup location (node 1)
- 1 delivery location (node 2)
- 1 vehicle
"""

import requests
import json

# API endpoint
url = "http://localhost:8000/solve_routes"

# Example input data
# This represents a simple problem:
# - Depot at node 0
# - Pickup at node 1 (demand: +1000 lbs)
# - Delivery at node 2 (demand: -1000 lbs)
# - Time matrix: travel times between nodes
# - Time windows for each node

example_input = {
    "time_matrix": [
        [0, 10, 25],    # From depot: 0 min to depot, 10 min to pickup, 25 min to delivery
        [10, 0, 15],    # From pickup: 10 min to depot, 0 min to pickup, 15 min to delivery
        [25, 15, 0]     # From delivery: 25 min to depot, 15 min to pickup, 0 min to delivery
    ],
    "pickups_deliveries": [
        [1, 2]  # Pickup at node 1, delivery at node 2
    ],
    "demands": [
        0,      # Depot: no load change
        1000,   # Pickup: +1000 lbs
        -1000   # Delivery: -1000 lbs
    ],
    "time_windows": [
        [0, 1440],   # Depot: available all day (0 to 1440 minutes)
        [60, 120],   # Pickup: must be visited between 60-120 minutes
        [180, 240]   # Delivery: must be visited between 180-240 minutes
    ],
    "num_vehicles": 1,
    "vehicle_capacity": 5000,  # 5000 lbs capacity
    "max_route_time": 1440,    # 24 hours max route time
    "depot_index": 0
}

def main():
    print("Sending request to VRPTW Solver API...")
    print(f"URL: {url}\n")
    
    try:
        response = requests.post(url, json=example_input)
        response.raise_for_status()
        
        result = response.json()
        
        print("=" * 60)
        print("SOLUTION RESULT")
        print("=" * 60)
        print(f"Solution Found: {result['solution_found']}")
        print(f"Message: {result['message']}\n")
        
        if result['solution_found']:
            print(f"Number of Routes: {len(result['routes'])}\n")
            
            for route in result['routes']:
                print(f"Route for Vehicle {route['vehicle_id']}:")
                print(f"  Total Route Time: {route['total_route_time_minutes']} minutes")
                print(f"  Number of Stops: {len(route['stops'])}")
                print("  Stops:")
                for stop in route['stops']:
                    print(f"    - Node {stop['node_index']}: "
                          f"Arrival at {stop['arrival_time_minutes']} min, "
                          f"Load: {stop['load_on_vehicle']} lbs")
                print()
        else:
            print("No feasible solution was found for the given constraints.")
            print("Try adjusting:")
            print("  - Time windows")
            print("  - Vehicle capacity")
            print("  - Number of vehicles")
            print("  - Maximum route time")
        
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API.")
        print("Make sure the FastAPI server is running:")
        print("  uvicorn main:app --reload")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

