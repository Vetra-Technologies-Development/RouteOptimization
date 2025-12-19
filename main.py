from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use environment variables only

# Gemini AI imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: google-generativeai not installed. Gemini features will be disabled.")

app = FastAPI(title="VRPTW Solver", description="Vehicle Routing Problem with Time Windows Solver")

# Initialize Gemini API if available
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_ENABLED = True
else:
    GEMINI_ENABLED = False
    if not GEMINI_AVAILABLE:
        print("Note: Install google-generativeai to enable Gemini features: pip install google-generativeai")
    elif not GEMINI_API_KEY:
        print("Note: Set GEMINI_API_KEY environment variable to enable Gemini features")


# Pydantic Model for Input Load Data
class LoadInput(BaseModel):
    # The adjacency matrix representing travel time in minutes between all nodes (including depots)
    time_matrix: List[List[int]]
    
    # List of tuples/lists defining [pickup_node_index, delivery_node_index]
    pickups_deliveries: List[List[int]]
    
    # List of demands (load change) for each node: Positive for pickup, Negative for delivery, Zero for depot.
    demands: List[int]
    
    # List of time windows for each node: [[earliest_start_min, latest_start_min], ...]
    time_windows: List[List[int]]
    
    # Configuration parameters
    num_vehicles: int
    vehicle_capacity: int  # Max weight in pounds
    max_route_time: int  # Max minutes for a single driver's shift (e.g., 1440 for 24 hours)
    depot_index: int = 0  # The index of the starting/ending depot node


# Pydantic Model for Output
class Stop(BaseModel):
    node_index: int
    arrival_time_minutes: int
    load_on_vehicle: int


class Route(BaseModel):
    vehicle_id: int
    total_route_time_minutes: int
    stops: List[Stop]


class RouteOption(BaseModel):
    """A single route option for the vehicle."""
    option_id: int
    total_route_time_minutes: int
    stops: List[Stop]
    description: Optional[str] = None


class SolutionResponse(BaseModel):
    routes: List[Route]  # For backward compatibility
    route_options: List[RouteOption] = []  # Multiple route options
    solution_found: bool
    message: Optional[str] = None
    num_options_found: int = 0


def create_data_model(load_input: LoadInput):
    """Create the data model for OR-Tools solver."""
    data = {}
    data['time_matrix'] = load_input.time_matrix
    data['num_vehicles'] = load_input.num_vehicles
    data['depot'] = load_input.depot_index
    data['demands'] = load_input.demands
    data['time_windows'] = load_input.time_windows
    data['vehicle_capacity'] = load_input.vehicle_capacity
    data['max_route_time'] = load_input.max_route_time
    data['pickups_deliveries'] = load_input.pickups_deliveries
    return data


def solve_vrptw_multiple_solutions(load_input: LoadInput, max_solutions: int = 5):
    """Solve the VRPTW problem and find multiple route options for a single vehicle."""
    # Create a copy of load_input with num_vehicles = 1
    load_input_single = LoadInput(
        time_matrix=load_input.time_matrix,
        pickups_deliveries=load_input.pickups_deliveries,
        demands=load_input.demands,
        time_windows=load_input.time_windows,
        num_vehicles=1,  # Force single vehicle
        vehicle_capacity=load_input.vehicle_capacity,
        max_route_time=load_input.max_route_time,
        depot_index=load_input.depot_index
    )
    
    solutions = []
    seen_routes = set()  # To avoid duplicate routes
    
    # Try different solution strategies to get multiple options
    # Use fewer strategies and shorter timeouts for faster results
    strategies = [
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC,
        routing_enums_pb2.FirstSolutionStrategy.SAVINGS,
    ]
    
    for strategy_idx, strategy in enumerate(strategies[:max_solutions]):
        try:
            # Use shorter timeout for multiple solution search
            solution, routing, manager, time_dimension, data_result = solve_vrptw(
                load_input_single, custom_strategy=strategy, timeout_seconds=10
            )
            if solution:
                routes = extract_solution(solution, routing, manager, time_dimension, data_result)
                if routes and len(routes) > 0:
                    route = routes[0]  # Single vehicle, so first route
                    # Create a signature to check for duplicates
                    route_signature = tuple([stop['node_index'] for stop in route['stops']])
                    if route_signature not in seen_routes:
                        seen_routes.add(route_signature)
                        solutions.append({
                            'option_id': len(solutions) + 1,
                            'total_route_time_minutes': route['total_route_time_minutes'],
                            'stops': route['stops'],
                            'strategy': strategy
                        })
        except Exception as e:
            # Silently skip failed strategies
            continue
    
    return solutions


def solve_vrptw(load_input: LoadInput, custom_strategy=None, timeout_seconds=None):
    """Solve the VRPTW problem using OR-Tools."""
    data = create_data_model(load_input)
    
    # Validate data before creating solver
    num_nodes = len(data['time_matrix'])
    if num_nodes == 0:
        raise Exception("Time matrix is empty")
    if data['depot'] < 0 or data['depot'] >= num_nodes:
        raise Exception(f"Invalid depot index: {data['depot']}")
    if data['num_vehicles'] <= 0:
        raise Exception(f"Invalid number of vehicles: {data['num_vehicles']}")
    
    # Warn about very large problems
    if num_nodes > 100:
        print(f"WARNING: Large problem detected ({num_nodes} nodes). Solver may take longer or fail.")
        print("Consider breaking the problem into smaller sub-problems if solver fails.")
    
    # Validate time windows
    for i, tw in enumerate(data['time_windows']):
        if len(tw) != 2:
            raise Exception(f"Invalid time window format at index {i}: {tw}")
        if tw[0] < 0 or tw[1] < 0:
            raise Exception(f"Negative time window at index {i}: {tw}")
        if tw[0] > tw[1]:
            raise Exception(f"Invalid time window (earliest > latest) at index {i}: {tw}")
    
    # Validate pickup/delivery pairs
    for pd in data['pickups_deliveries']:
        if len(pd) != 2:
            raise Exception(f"Invalid pickup/delivery pair: {pd}")
        if pd[0] < 0 or pd[0] >= num_nodes:
            raise Exception(f"Invalid pickup index: {pd[0]}")
        if pd[1] < 0 or pd[1] >= num_nodes:
            raise Exception(f"Invalid delivery index: {pd[1]}")
        if pd[0] == pd[1]:
            raise Exception(f"Pickup and delivery cannot be the same node: {pd}")
    
    # Validate time matrix
    for i, row in enumerate(data['time_matrix']):
        if len(row) != num_nodes:
            raise Exception(f"Time matrix row {i} has incorrect length: {len(row)} != {num_nodes}")
        for j, time_val in enumerate(row):
            if time_val < 0:
                raise Exception(f"Negative time in time matrix at [{i}][{j}]: {time_val}")
            if i == j and time_val != 0:
                raise Exception(f"Diagonal time matrix value should be 0 at [{i}][{j}]: {time_val}")
    
    # Create the routing index manager
    try:
        manager = pywrapcp.RoutingIndexManager(
            num_nodes,
            data['num_vehicles'],
            data['depot']
        )
    except Exception as e:
        raise Exception(f"Failed to create routing index manager: {str(e)}")
    
    # Create routing model
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register a transit callback
    def time_callback(from_index, to_index):
        """Returns the travel time between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node]
    
    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # Define cost of each arc
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Add Time Window constraint
    def time_callback_with_wait(from_index, to_index):
        """Returns the travel time plus wait time if needed."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel_time = data['time_matrix'][from_node][to_node]
        return travel_time
    
    time_callback_index = routing.RegisterTransitCallback(time_callback_with_wait)
    
    # Add time dimension
    time = 'Time'
    routing.AddDimension(
        time_callback_index,
        30,  # allow waiting time
        data['max_route_time'],  # maximum time per vehicle
        False,  # Don't force start cumul to zero
        time
    )
    time_dimension = routing.GetDimensionOrDie(time)
    
    # Add time window constraints for each location
    for location_idx, time_window in enumerate(data['time_windows']):
        if location_idx == data['depot']:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
    
    # Add time window constraints for depot (start and end)
    depot_idx = manager.NodeToIndex(data['depot'])
    time_dimension.CumulVar(depot_idx).SetRange(0, data['max_route_time'])
    
    # Add capacity constraint
    def demand_callback(from_index):
        """Returns the demand of the node."""
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        [data['vehicle_capacity']] * data['num_vehicles'],  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity'
    )
    
    # Add pickup and delivery constraints
    for pickup_delivery in data['pickups_deliveries']:
        pickup_index = manager.NodeToIndex(pickup_delivery[0])
        delivery_index = manager.NodeToIndex(pickup_delivery[1])
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        routing.solver().Add(
            routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index)
        )
        routing.solver().Add(
            time_dimension.CumulVar(pickup_index) <=
            time_dimension.CumulVar(delivery_index)
        )
    
    # Setting first solution heuristic
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    num_nodes = len(data['time_matrix'])
    
    # Use custom strategy if provided, otherwise use automatic
    if custom_strategy is not None:
        search_parameters.first_solution_strategy = custom_strategy
    elif num_nodes > 100:
        # Use a simpler strategy for large problems
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
    else:
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
        )
    
    # Set local search metaheuristic
    if timeout_seconds is not None:
        search_parameters.time_limit.seconds = timeout_seconds
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
    elif num_nodes > 100:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH
        )
        search_parameters.time_limit.seconds = 180  # 3 minutes for very large problems
    elif num_nodes > 50:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 120  # 2 minutes for large problems
    else:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 30
    
    # Solve the problem
    try:
        solution = routing.SolveWithParameters(search_parameters)
    except Exception as e:
        # Log more details about the error
        error_msg = f"OR-Tools solver error: {str(e)}"
        print(f"DEBUG: {error_msg}")
        raise Exception(error_msg)
    
    return solution, routing, manager, time_dimension, data


def extract_solution(solution, routing, manager, time_dimension, data):
    """Extract the solution from OR-Tools and format it."""
    routes = []
    
    if solution is None:
        return routes
    
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        route_stops = []
        total_route_time = 0
        current_load = 0
        
        # Skip the starting depot
        index = solution.Value(routing.NextVar(index))
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            arrival_time = solution.Value(time_var)
            
            # Update load (demand is applied when visiting the node)
            current_load += data['demands'][node_index]
            
            route_stops.append({
                'node_index': node_index,
                'arrival_time_minutes': arrival_time,
                'load_on_vehicle': current_load
            })
            
            # Get next index
            index = solution.Value(routing.NextVar(index))
        
        # Get the end depot time for total route time
        node_index = manager.IndexToNode(index)
        time_var = time_dimension.CumulVar(index)
        arrival_time = solution.Value(time_var)
        total_route_time = arrival_time
        
        # Only add route if it has stops (excluding just depot)
        if len(route_stops) > 0:
            routes.append({
                'vehicle_id': vehicle_id,
                'total_route_time_minutes': total_route_time,
                'stops': route_stops
            })
    
    return routes


@app.post("/solve_routes", response_model=SolutionResponse)
async def solve_routes(load_input: LoadInput):
    """
    Solve the Vehicle Routing Problem with Time Windows (VRPTW).
    
    This endpoint accepts routing problem parameters and returns optimal routes
    that satisfy all constraints including time windows, capacity, and pickup/delivery precedence.
    """
    try:
        # Validate input
        num_nodes = len(load_input.time_matrix)
        if num_nodes == 0:
            raise HTTPException(status_code=400, detail="Time matrix cannot be empty")
        
        if len(load_input.demands) != num_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Demands length ({len(load_input.demands)}) must match time matrix size ({num_nodes})"
            )
        
        if len(load_input.time_windows) != num_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Time windows length ({len(load_input.time_windows)}) must match time matrix size ({num_nodes})"
            )
        
        if load_input.depot_index < 0 or load_input.depot_index >= num_nodes:
            raise HTTPException(
                status_code=400,
                detail=f"Depot index {load_input.depot_index} is out of range [0, {num_nodes-1}]"
            )
        
        # Validate pickup/delivery pairs
        for pickup_delivery in load_input.pickups_deliveries:
            if len(pickup_delivery) != 2:
                raise HTTPException(
                    status_code=400,
                    detail="Each pickup/delivery pair must have exactly 2 elements [pickup_index, delivery_index]"
                )
            pickup_idx, delivery_idx = pickup_delivery
            if pickup_idx < 0 or pickup_idx >= num_nodes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pickup index {pickup_idx} is out of range"
                )
            if delivery_idx < 0 or delivery_idx >= num_nodes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Delivery index {delivery_idx} is out of range"
                )
        
        # Solve the problem
        try:
            solution, routing, manager, time_dimension, data = solve_vrptw(load_input)
        except Exception as e:
            error_detail = str(e)
            # Check if it's a known OR-Tools error
            if "CP Solver fail" in error_detail or "fail" in error_detail.lower():
                return SolutionResponse(
                    routes=[],
                    route_options=[],
                    solution_found=False,
                    message=f"Solver failed to initialize. This may be due to problem size or constraint conflicts. Error: {error_detail}",
                    num_options_found=0
                )
            raise HTTPException(status_code=500, detail=f"Solver error: {error_detail}")
        
        if solution is None:
            return SolutionResponse(
                routes=[],
                route_options=[],
                solution_found=False,
                message="No feasible solution found for the given constraints.",
                num_options_found=0
            )
        
        # Extract solution
        routes = extract_solution(solution, routing, manager, time_dimension, data)
        
        # If single vehicle, try to find multiple route options (but don't block on it)
        route_options_list = []
        if load_input.num_vehicles == 1 and solution:
            try:
                # Try to get multiple options, but use short timeout
                route_options = solve_vrptw_multiple_solutions(load_input, max_solutions=3)
                
                # Convert route options
                route_options_list = []
                for opt in route_options:
                    route_options_list.append(RouteOption(
                        option_id=opt['option_id'],
                        total_route_time_minutes=opt['total_route_time_minutes'],
                        stops=[Stop(**stop) for stop in opt['stops']],
                        description=f"Route option {opt['option_id']}"
                    ))
                
                # Sort by route time (best first)
                route_options_list.sort(key=lambda x: x.total_route_time_minutes)
                
                # Also add the first solution as an option if not already included
                if routes and len(routes) > 0:
                    first_route = routes[0]
                    first_signature = tuple([stop['node_index'] for stop in first_route['stops']])
                    if not any(tuple([stop.node_index for stop in opt.stops]) == first_signature 
                              for opt in route_options_list):
                        route_options_list.insert(0, RouteOption(
                            option_id=0,
                            total_route_time_minutes=first_route['total_route_time_minutes'],
                            stops=[Stop(**stop) for stop in first_route['stops']],
                            description="Primary route"
                        ))
                
                return SolutionResponse(
                    routes=[Route(**route) for route in routes],
                    route_options=route_options_list,
                    solution_found=True,
                    message=f"Found {len(route_options_list)} route options.",
                    num_options_found=len(route_options_list)
                )
            except Exception as e:
                # If multiple solutions fail, return single solution
                print(f"Warning: Could not find multiple solutions: {e}")
                return SolutionResponse(
                    routes=[Route(**route) for route in routes],
                    route_options=[],
                    solution_found=True,
                    message="Solution found successfully (single route).",
                    num_options_found=len(routes)
                )
        else:
            return SolutionResponse(
                routes=[Route(**route) for route in routes],
                route_options=[],
                solution_found=True,
                message="Solution found successfully.",
                num_options_found=len(routes)
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "VRPTW Solver API",
        "endpoints": {
            "/solve_routes": "POST - Solve Vehicle Routing Problem with Time Windows",
            "/get_all_routes": "POST - Get all possible route chains from search criteria (use ?include_trip_plans=true for Gemini AI planning)"
        },
        "gemini_enabled": GEMINI_ENABLED
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Pydantic Models for All Routes Endpoint
class LocationInput(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None
    state: Optional[str] = None


class TimeWindowInput(BaseModel):
    earliest: str
    latest: str


class RevenueInput(BaseModel):
    amount: Optional[float] = 0
    rate_per_mile: Optional[float] = None


class LoadInputRaw(BaseModel):
    id: Optional[str] = None
    origin: LocationInput
    destination: LocationInput
    pickupWindow: TimeWindowInput
    deliveryWindow: TimeWindowInput
    distanceMiles: Optional[float] = 0
    estimatedDurationMinutes: Optional[int] = 0
    revenue: Optional[RevenueInput] = None
    requirements: Optional[Dict[str, Any]] = None


class SearchCriteriaInput(BaseModel):
    origin: LocationInput
    destination: Optional[LocationInput] = None
    options: Optional[Dict[str, Any]] = None


class AllRoutesRequest(BaseModel):
    searchCriteria: SearchCriteriaInput
    loads: List[LoadInputRaw]


class RouteSegment(BaseModel):
    load_id: Optional[str]
    origin: str
    destination: str
    distance_miles: float
    revenue: float
    rate_per_mile: Optional[float] = None
    pickup_window: Dict[str, str]
    delivery_window: Dict[str, str]
    weight_pounds: Optional[float] = None
    deadhead_before: float


class RouteOption(BaseModel):
    route_id: int
    segments: List[RouteSegment]
    total_distance: float
    total_revenue: float
    total_deadhead: float
    ends_near_destination: bool
    final_distance_to_dest: Optional[float] = None


class TripPlanDetail(BaseModel):
    """Detailed trip plan generated by Gemini AI."""
    route_id: int
    summary: str
    detailed_plan: str
    estimated_duration_hours: Optional[float] = None
    recommendations: Optional[List[str]] = None
    potential_issues: Optional[List[str]] = None
    fuel_stops: Optional[List[str]] = None
    rest_stops: Optional[List[str]] = None


class AllRoutesResponse(BaseModel):
    total_routes: int
    routes: List[RouteOption]
    search_criteria: Dict[str, Any]
    message: Optional[str] = None
    trip_plans: Optional[List[TripPlanDetail]] = None


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


def can_chain_loads(load1: Dict, load2: Dict, max_deadhead: float = 100) -> Tuple[bool, float]:
    """Check if load2 can be chained after load1. Returns (can_chain, deadhead_miles)."""
    deliv1 = load1['destination']
    pickup2 = load2['origin']
    
    deadhead = haversine_distance(
        deliv1['latitude'], deliv1['longitude'],
        pickup2['latitude'], pickup2['longitude']
    )
    
    if deadhead > max_deadhead:
        return False, deadhead
    
    # Check time windows - use snake_case keys (delivery_window, pickup_window)
    delivery_window = load1.get('delivery_window', {})
    pickup_window = load2.get('pickup_window', {})
    
    if not delivery_window or not pickup_window:
        return False, deadhead
    
    load1_delivery_earliest = parse_iso_to_minutes(delivery_window.get('earliest', ''))
    load1_delivery_latest = parse_iso_to_minutes(delivery_window.get('latest', ''))
    load2_pickup_earliest = parse_iso_to_minutes(pickup_window.get('earliest', ''))
    load2_pickup_latest = parse_iso_to_minutes(pickup_window.get('latest', ''))
    
    deadhead_time = max(30, int((deadhead / 50) * 60))
    buffer_time = 1440 * 5  # 5 days buffer
    
    if load1_delivery_latest + deadhead_time > load2_pickup_latest + buffer_time:
        return False, deadhead
    
    if load1_delivery_earliest + deadhead_time > load2_pickup_latest + buffer_time + 1440:
        return False, deadhead
    
    return True, deadhead


def generate_trip_plan_with_gemini(route: RouteOption, search_criteria: Dict[str, Any]) -> Optional[TripPlanDetail]:
    """Generate detailed trip plan using Gemini AI."""
    if not GEMINI_ENABLED:
        return None
    
    try:
        # Prepare route information for Gemini
        origin = search_criteria.get('origin', {})
        destination = search_criteria.get('destination', {})
        
        route_info = f"""
Route ID: {route.route_id}
Total Distance: {route.total_distance:.0f} miles
Total Revenue: ${route.total_revenue:.2f}
Total Deadhead: {route.total_deadhead:.0f} miles
Number of Segments: {len(route.segments)}

Origin: {origin.get('city', 'Unknown')}, {origin.get('state', '')}
Destination: {destination.get('city', 'Unknown') if destination else 'N/A'}, {destination.get('state', '') if destination else ''}

Route Segments:
"""
        
        for i, segment in enumerate(route.segments, 1):
            route_info += f"""
Segment {i}:
  - From: {segment.origin}
  - To: {segment.destination}
  - Distance: {segment.distance_miles:.0f} miles
  - Revenue: ${segment.revenue:.2f}
  - Deadhead before segment: {segment.deadhead_before:.1f} miles
  - Pickup Window: {segment.pickup_window.get('earliest', 'N/A')} to {segment.pickup_window.get('latest', 'N/A')}
  - Delivery Window: {segment.delivery_window.get('earliest', 'N/A')} to {segment.delivery_window.get('latest', 'N/A')}
  - Weight: {segment.weight_pounds or 'N/A'} lbs
"""
        
        prompt = f"""You are a professional trucking route planner. Analyze the following route and provide a detailed trip plan.

{route_info}

Please provide a comprehensive trip plan that includes:
1. A brief summary of the route (2-3 sentences)
2. Detailed day-by-day itinerary with estimated travel times
3. Recommended fuel stops along the route
4. Recommended rest stops (considering DOT hours of service regulations)
5. Potential issues or challenges (weather, traffic, road conditions)
6. Tips for optimizing this route
7. Estimated total driving time and rest time needed

Format your response as a structured trip plan that a truck driver can follow. Be specific about locations, timing, and recommendations."""
        
        # Use Gemini Pro model
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        plan_text = response.text
        
        # Parse the response to extract structured information
        recommendations = []
        potential_issues = []
        fuel_stops = []
        rest_stops = []
        estimated_duration = None
        
        # Simple parsing (can be enhanced)
        lines = plan_text.split('\n')
        current_section = None
        for line in lines:
            line_lower = line.lower()
            if 'fuel' in line_lower or 'gas' in line_lower:
                fuel_stops.append(line.strip())
            if 'rest' in line_lower or 'sleep' in line_lower or 'hotel' in line_lower:
                rest_stops.append(line.strip())
            if 'issue' in line_lower or 'challenge' in line_lower or 'warning' in line_lower:
                potential_issues.append(line.strip())
            if 'recommend' in line_lower or 'tip' in line_lower or 'suggest' in line_lower:
                recommendations.append(line.strip())
            if 'hour' in line_lower and ('total' in line_lower or 'estimate' in line_lower):
                # Try to extract hours
                import re
                hours_match = re.search(r'(\d+(?:\.\d+)?)\s*hours?', line_lower)
                if hours_match:
                    estimated_duration = float(hours_match.group(1))
        
        # Extract summary (first paragraph)
        summary = plan_text.split('\n\n')[0] if '\n\n' in plan_text else plan_text[:200]
        
        return TripPlanDetail(
            route_id=route.route_id,
            summary=summary,
            detailed_plan=plan_text,
            estimated_duration_hours=estimated_duration,
            recommendations=recommendations[:5] if recommendations else None,
            potential_issues=potential_issues[:5] if potential_issues else None,
            fuel_stops=fuel_stops[:5] if fuel_stops else None,
            rest_stops=rest_stops[:5] if rest_stops else None
        )
    
    except Exception as e:
        print(f"Error generating trip plan with Gemini: {e}")
        return None


def find_all_routes_from_request(request: AllRoutesRequest, max_chain_length: int = 5) -> List[Dict]:
    """Find all possible route chains from the request data."""
    search_criteria = request.searchCriteria
    loads = request.loads
    
    # Convert Pydantic models to dicts for processing
    loads_dict = []
    for load in loads:
        load_dict = {
            'load_id': load.id or f"load_{len(loads_dict)}",
            'origin': {
                'latitude': load.origin.latitude,
                'longitude': load.origin.longitude,
                'city': load.origin.city or 'Unknown',
                'state': load.origin.state or ''
            },
            'destination': {
                'latitude': load.destination.latitude,
                'longitude': load.destination.longitude,
                'city': load.destination.city or 'Unknown',
                'state': load.destination.state or ''
            },
            'pickup_window': {
                'earliest': load.pickupWindow.earliest,
                'latest': load.pickupWindow.latest
            },
            'delivery_window': {
                'earliest': load.deliveryWindow.earliest,
                'latest': load.deliveryWindow.latest
            },
            'distance_miles': load.distanceMiles or 0,
            'revenue': {
                'amount': load.revenue.amount if load.revenue else 0,
                'rate_per_mile': load.revenue.rate_per_mile if load.revenue else None
            },
            'weight_pounds': load.requirements.get('weightPounds') if load.requirements else None
        }
        loads_dict.append(load_dict)
    
    origin = search_criteria.origin
    destination = search_criteria.destination
    
    origin_lat = origin.latitude
    origin_lon = origin.longitude
    origin_city = origin.city or 'Origin'
    origin_state = origin.state or ''
    
    dest_lat = destination.latitude if destination else None
    dest_lon = destination.longitude if destination else None
    dest_city = destination.city if destination else None
    dest_state = destination.state if destination else None
    
    # Get max deadhead from options
    max_deadhead = 100
    if search_criteria.options:
        max_deadhead = search_criteria.options.get('maxOriginDeadheadMiles', 100)
    
    # Find loads that start near origin
    starting_loads = []
    for load in loads_dict:
        pickup_lat = load['origin']['latitude']
        pickup_lon = load['origin']['longitude']
        distance = haversine_distance(origin_lat, origin_lon, pickup_lat, pickup_lon)
        if distance <= max_deadhead:
            starting_loads.append((load, distance))
    
    starting_loads.sort(key=lambda x: x[1])
    
    # Build chain graph
    chain_graph = defaultdict(list)
    for i, load1 in enumerate(loads_dict):
        for j, load2 in enumerate(loads_dict):
            if i != j:
                can_chain, deadhead = can_chain_loads(load1, load2, max_deadhead)
                if can_chain:
                    chain_graph[load1['load_id']].append((load2, deadhead))
    
    # Find all routes using DFS
    all_routes = []
    processed_chains = set()
    
    def dfs_route(current_chain: List[Tuple[Dict, float]], current_load: Dict, depth: int):
        """Depth-first search to find all route chains."""
        if depth > max_chain_length:
            return
        
        # Check if current chain ends near destination
        if dest_lat and dest_lon:
            final_deliv = current_load['destination']
            distance_to_dest = haversine_distance(
                final_deliv['latitude'], final_deliv['longitude'],
                dest_lat, dest_lon
            )
            
            if distance_to_dest <= max_deadhead:
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
                        'weight_pounds': load.get('weight_pounds'),
                        'deadhead_before': deadhead
                    })
                    route['total_distance'] += load['distance_miles']
                    route['total_revenue'] += load['revenue']['amount']
                    route['total_deadhead'] += deadhead
                
                chain_sig = tuple(l[0]['load_id'] for l in current_chain)
                if chain_sig not in processed_chains:
                    all_routes.append(route)
                    processed_chains.add(chain_sig)
        
        # Try to extend chain
        if current_load['load_id'] in chain_graph:
            for next_load, deadhead in chain_graph[current_load['load_id']]:
                if not any(l[0]['load_id'] == next_load['load_id'] for l in current_chain):
                    dfs_route(current_chain + [(next_load, deadhead)], next_load, depth + 1)
    
    # Start DFS from each starting load
    for start_load, start_deadhead in starting_loads:
        chain_signature = (start_load['load_id'],)
        if chain_signature not in processed_chains:
            dfs_route([(start_load, start_deadhead)], start_load, 1)
            processed_chains.add(chain_signature)
    
    # Also add single-load routes that go directly to destination
    if dest_lat and dest_lon:
        for load in loads_dict:
            deliv = load['destination']
            distance_to_dest = haversine_distance(
                deliv['latitude'], deliv['longitude'],
                dest_lat, dest_lon
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
                            'weight_pounds': load.get('weight_pounds'),
                            'deadhead_before': start_distance
                        }],
                        'total_distance': load['distance_miles'],
                        'total_revenue': load['revenue']['amount'],
                        'total_deadhead': start_distance,
                        'ends_near_destination': True,
                        'final_distance_to_dest': distance_to_dest
                    }
                    all_routes.append(route)
    
    # Remove duplicates
    unique_routes = []
    seen_signatures = set()
    for route in all_routes:
        sig = tuple((s['origin'], s['destination']) for s in route['segments'])
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_routes.append(route)
    
    # Sort by revenue (highest first), then by distance (shortest first)
    unique_routes.sort(key=lambda x: (-x['total_revenue'], x['total_distance']))
    
    # Renumber routes
    for i, route in enumerate(unique_routes):
        route['route_id'] = i + 1
    
    return unique_routes


@app.post("/get_all_routes", response_model=AllRoutesResponse)
async def get_all_routes(request: AllRoutesRequest, include_trip_plans: bool = False):
    """
    Get all possible route chains from search criteria origin to destination.
    
    This endpoint accepts raw JSON with searchCriteria and loads structure,
    and returns all possible route chains that satisfy the constraints.
    
    Args:
        request: The route request with searchCriteria and loads
        include_trip_plans: If True, generate detailed trip plans using Gemini AI (requires GEMINI_API_KEY)
    """
    try:
        # Validate input
        if not request.loads:
            raise HTTPException(status_code=400, detail="No loads provided")
        
        if not request.searchCriteria.origin:
            raise HTTPException(status_code=400, detail="Search criteria must include origin")
        
        # Find all routes
        routes = find_all_routes_from_request(request, max_chain_length=10)
        
        # Convert to response format
        route_options = []
        for route in routes:
            segments = []
            for seg in route['segments']:
                segments.append(RouteSegment(
                    load_id=seg.get('load_id'),
                    origin=seg['origin'],
                    destination=seg['destination'],
                    distance_miles=seg['distance_miles'],
                    revenue=seg['revenue'],
                    rate_per_mile=seg.get('rate_per_mile'),
                    pickup_window=seg['pickup_window'],
                    delivery_window=seg['delivery_window'],
                    weight_pounds=seg.get('weight_pounds'),
                    deadhead_before=seg['deadhead_before']
                ))
            
            route_options.append(RouteOption(
                route_id=route['route_id'],
                segments=segments,
                total_distance=route['total_distance'],
                total_revenue=route['total_revenue'],
                total_deadhead=route['total_deadhead'],
                ends_near_destination=route.get('ends_near_destination', False),
                final_distance_to_dest=route.get('final_distance_to_dest')
            ))
        
        # Generate trip plans with Gemini if requested
        trip_plans = None
        if include_trip_plans:
            if not GEMINI_ENABLED:
                raise HTTPException(
                    status_code=400,
                    detail="Gemini AI is not enabled. Set GEMINI_API_KEY environment variable and install google-generativeai package."
                )
            
            trip_plans = []
            search_criteria_dict = {
                'origin': {
                    'city': request.searchCriteria.origin.city,
                    'state': request.searchCriteria.origin.state,
                    'latitude': request.searchCriteria.origin.latitude,
                    'longitude': request.searchCriteria.origin.longitude
                },
                'destination': {
                    'city': request.searchCriteria.destination.city if request.searchCriteria.destination else None,
                    'state': request.searchCriteria.destination.state if request.searchCriteria.destination else None,
                    'latitude': request.searchCriteria.destination.latitude if request.searchCriteria.destination else None,
                    'longitude': request.searchCriteria.destination.longitude if request.searchCriteria.destination else None
                } if request.searchCriteria.destination else None,
                'options': request.searchCriteria.options or {}
            }
            
            # Generate plans for top 5 routes (to avoid too many API calls)
            for route_option in route_options[:5]:
                plan = generate_trip_plan_with_gemini(route_option, search_criteria_dict)
                if plan:
                    trip_plans.append(plan)
        
        return AllRoutesResponse(
            total_routes=len(route_options),
            routes=route_options,
            search_criteria={
                'origin': {
                    'city': request.searchCriteria.origin.city,
                    'state': request.searchCriteria.origin.state,
                    'latitude': request.searchCriteria.origin.latitude,
                    'longitude': request.searchCriteria.origin.longitude
                },
                'destination': {
                    'city': request.searchCriteria.destination.city if request.searchCriteria.destination else None,
                    'state': request.searchCriteria.destination.state if request.searchCriteria.destination else None,
                    'latitude': request.searchCriteria.destination.latitude if request.searchCriteria.destination else None,
                    'longitude': request.searchCriteria.destination.longitude if request.searchCriteria.destination else None
                } if request.searchCriteria.destination else None,
                'options': request.searchCriteria.options or {}
            },
            message=f"Found {len(route_options)} possible routes" + (" with detailed trip plans" if trip_plans else ""),
            trip_plans=trip_plans
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

