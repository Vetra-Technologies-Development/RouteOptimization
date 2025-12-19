"""
Script to solve large VRPTW problems by breaking them into smaller chunks.
"""

import json
import requests
from process_boston_dallas import process_loads_data

API_URL = "http://localhost:8000/solve_routes"


def solve_chunk(chunk_data, chunk_num):
    """Solve a single chunk of the problem."""
    print(f"\n{'='*60}")
    print(f"Solving Chunk {chunk_num}")
    print(f"{'='*60}")
    print(f"Nodes: {len(chunk_data['time_matrix'])}")
    print(f"Loads: {len(chunk_data['pickups_deliveries'])}")
    print(f"Vehicles: {chunk_data['num_vehicles']}")
    
    request_data = {k: v for k, v in chunk_data.items() if k != 'locations'}
    
    try:
        response = requests.post(API_URL, json=request_data, timeout=300)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"Error solving chunk {chunk_num}: {e}")
        return None


def main():
    import sys
    
    chunk_size = 20  # Number of loads per chunk
    if len(sys.argv) > 1:
        try:
            chunk_size = int(sys.argv[1])
        except ValueError:
            pass
    
    print("Processing boston-dallas-20.json in chunks...")
    print(f"Chunk size: {chunk_size} loads per chunk")
    print("=" * 60)
    
    # Process all loads to get the full dataset
    full_data = process_loads_data('boston-dallas-20.json')
    all_loads = len(full_data['pickups_deliveries'])
    
    print(f"\nTotal loads: {all_loads}")
    print(f"Number of chunks: {(all_loads + chunk_size - 1) // chunk_size}")
    
    # For now, let's try solving with a smaller subset first
    # to see if the solver works with manageable sizes
    test_sizes = [10, 20, 30, 50]
    
    for test_size in test_sizes:
        if test_size > all_loads:
            continue
        
        print(f"\n{'='*60}")
        print(f"Testing with {test_size} loads...")
        print(f"{'='*60}")
        
        test_data = process_loads_data('boston-dallas-20.json', max_loads=test_size)
        
        result = solve_chunk(test_data, test_size)
        
        if result and result.get('solution_found'):
            print(f"✓ Successfully solved with {test_size} loads!")
            print(f"  Routes found: {len(result.get('routes', []))}")
        elif result:
            print(f"✗ No solution found for {test_size} loads")
        else:
            print(f"✗ Solver failed for {test_size} loads")
            break  # Stop if solver fails
    
    print("\n" + "=" * 60)
    print("Recommendation:")
    print("If solver fails for large problems, consider:")
    print("1. Breaking the problem into geographic regions")
    print("2. Solving by time windows (earlier loads first)")
    print("3. Using a commercial solver for very large problems")
    print("4. Relaxing constraints (wider time windows, more vehicles)")


if __name__ == "__main__":
    main()

