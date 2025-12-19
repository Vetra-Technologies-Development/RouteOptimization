# VRPTW Solver API

A FastAPI-based Vehicle Routing Problem with Time Windows (VRPTW) solver that finds optimal multi-load chaining routes using Google OR-Tools.

## Features

- **Time Window Constraints**: Ensures all stops are visited within their specified time windows
- **Capacity Constraints**: Tracks vehicle load and ensures it never exceeds maximum capacity
- **Pickup/Delivery Precedence**: Ensures pickups are always visited before their corresponding deliveries, and both are handled by the same vehicle
- **Route Time Limits**: Enforces maximum route time per vehicle
- **Multi-Vehicle Support**: Solves problems with multiple vehicles
- **All Possible Routes**: Find all feasible route chains using graph-based search
- **Gemini AI Integration**: Generate detailed trip plans with fuel stops, rest stops, and recommendations (optional)

## Installation

1. Install Python 3.8 or higher
2. Create a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

See [SETUP.md](SETUP.md) for detailed setup instructions.

## Running the Application

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Alternative API Docs: `http://localhost:8000/redoc`

## API Endpoints

### POST `/solve_routes`

Solves a Vehicle Routing Problem with Time Windows using OR-Tools optimization.

#### Request Body Schema

```json
{
  "time_matrix": [[0, 10, 20], [10, 0, 15], [20, 15, 0]],
  "pickups_deliveries": [[1, 2]],
  "demands": [0, 1000, -1000],
  "time_windows": [[0, 1440], [60, 120], [180, 240]],
  "num_vehicles": 1,
  "vehicle_capacity": 5000,
  "max_route_time": 1440,
  "depot_index": 0
}
```

#### Response Schema

```json
{
  "routes": [
    {
      "vehicle_id": 0,
      "total_route_time_minutes": 240,
      "stops": [
        {
          "node_index": 1,
          "arrival_time_minutes": 60,
          "load_on_vehicle": 1000
        },
        {
          "node_index": 2,
          "arrival_time_minutes": 180,
          "load_on_vehicle": 0
        }
      ]
    }
  ],
  "solution_found": true,
  "message": "Solution found successfully."
}
```

## Input Parameters

- **time_matrix**: Square matrix where `time_matrix[i][j]` represents travel time in minutes from node `i` to node `j`
- **pickups_deliveries**: List of `[pickup_index, delivery_index]` pairs
- **demands**: List of load changes at each node (positive for pickup, negative for delivery, zero for depot)
- **time_windows**: List of `[earliest_start_min, latest_start_min]` for each node
- **num_vehicles**: Number of available vehicles
- **vehicle_capacity**: Maximum weight capacity per vehicle (in pounds)
- **max_route_time**: Maximum route time per vehicle in minutes (e.g., 1440 for 24 hours)
- **depot_index**: Index of the depot node (default: 0)

### POST `/get_all_routes`

Get all possible route chains from search criteria. Accepts raw JSON with `searchCriteria` and `loads` structure.

**Query Parameters:**
- `include_trip_plans` (optional): If `true`, generates detailed trip plans using Gemini AI (requires `GEMINI_API_KEY`)

**Request Body:**
```json
{
  "searchCriteria": {
    "origin": {
      "latitude": 42.3601,
      "longitude": -71.0589,
      "city": "Boston",
      "state": "MA"
    },
    "destination": {
      "latitude": 32.7767,
      "longitude": -96.7970,
      "city": "Dallas",
      "state": "TX"
    }
  },
  "loads": [...]
}
```

See [GEMINI_SETUP.md](GEMINI_SETUP.md) for Gemini AI setup instructions.

## Example Usage

- `example_usage.py` - Basic VRPTW solver example
- `example_get_all_routes.py` - Get all possible routes with optional Gemini AI trip planning

## Constraints

The solver enforces:

1. **Time Windows**: Each node must be visited within its specified time window
2. **Capacity**: Vehicle load never exceeds `vehicle_capacity`
3. **Pickup/Delivery**: Pickups must be visited before their deliveries, and both must be on the same vehicle
4. **Route Time**: Each route's total time cannot exceed `max_route_time`

