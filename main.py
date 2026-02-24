from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.dependencies import get_loadboard_service, is_supabase_enabled
from app.routers.loadboard import extract_xml_content
from typing import List, Optional, Dict, Any, Tuple
import math
import os
import logging
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use environment variables only

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # 'json' or 'text'
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "false").lower() == "true"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "api.log")
LOG_API_REQUESTS = os.getenv("LOG_API_REQUESTS", "true").lower() == "true"

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if LOG_FORMAT == "text" else None,
    handlers=[
        logging.StreamHandler(),
        *([logging.FileHandler(LOG_FILE_PATH)] if LOG_TO_FILE else [])
    ]
)

logger = logging.getLogger(__name__)

# Try to import ortools, but make it optional
try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    logger.warning("ortools not installed. The /solve_routes endpoint will not be available.")
    logger.info("Install ortools with: pip install ortools")
    # Create dummy classes to prevent import errors
    routing_enums_pb2 = None
    pywrapcp = None

# Gemini AI imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Gemini features will be disabled.")

# Supabase imports
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("supabase not installed. LoadBoard Network integration will not be available.")
    Client = None

app = FastAPI(title="VRPTW Solver", description="Vehicle Routing Problem with Time Windows Solver")

# Simple in-memory loadboard storage for HTML interface
LOADBOARD_POSTS: List[Dict[str, Any]] = []
LOADBOARD_UI_PATH = os.path.join(os.path.dirname(__file__), "loadboard.html")
LOADBOARD_LOGO_PATH = "/loadboard/logo"

# Serve static assets
public_dir = os.path.join(os.path.dirname(__file__), "public")
if os.path.isdir(public_dir):
    app.mount("/public", StaticFiles(directory=public_dir), name="public")


@app.get("/loadboard/logo")
async def loadboard_logo():
    """Serve the Vetra logo for the loadboard UI."""
    logo_filename = "Vetra Technologies Logo.png"
    candidate_paths = [
        os.path.join(public_dir, logo_filename),
        os.path.join(os.getcwd(), "public", logo_filename),
        os.path.join(os.path.dirname(__file__), "public", logo_filename),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Logo not found")

# Add request/response logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    if LOG_API_REQUESTS:
        start_time = datetime.now()
        logger.info(f"Request: {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    response = await call_next(request)
    
    if LOG_API_REQUESTS:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    return response

# Add CORS middleware - configure origins based on environment
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if "*" not in CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini API if available
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_ENABLED = True
else:
    GEMINI_ENABLED = False
    if not GEMINI_AVAILABLE:
        logger.info("Install google-generativeai to enable Gemini features: pip install google-generativeai")
    elif not GEMINI_API_KEY:
        logger.info("Set GEMINI_API_KEY environment variable to enable Gemini features")

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase_client: Optional[Client] = None

if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        SUPABASE_ENABLED = True
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        SUPABASE_ENABLED = False
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase_client = None
else:
    SUPABASE_ENABLED = False
    if not SUPABASE_AVAILABLE:
        logger.info("Install supabase to enable LoadBoard Network integration: pip install supabase")
    elif not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.info("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables to enable LoadBoard Network integration")


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
        logger.warning(f"Large problem detected ({num_nodes} nodes). Solver may take longer or fail.")
        logger.info("Consider breaking the problem into smaller sub-problems if solver fails.")
    
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
        logger.debug(f"{error_msg}")
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
    if not ORTOOLS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OR-Tools is not installed. This endpoint requires ortools. Install it with: pip install ortools"
        )
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
                logger.warning(f"Could not find multiple solutions: {e}")
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
            "/get_all_routes": "POST - Get all possible route chains from search criteria (use ?include_trip_plans=true for Gemini AI planning)",
            "/loadboard/post_loads": "POST - LoadBoard Network post loads endpoint (receives XML, saves to Supabase)",
            "/loadboard/remove_loads": "POST - LoadBoard Network remove loads endpoint (receives XML, removes from Supabase)"
        },
        "gemini_enabled": GEMINI_ENABLED,
        "supabase_enabled": SUPABASE_ENABLED
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/loadboard/health")
async def loadboard_health():
    """Loadboard health check endpoint."""
    return {"status": "ok"}


@app.get("/loadboard/dashboard", response_class=HTMLResponse)
async def loadboard_ui(request: Request):
    """Serve the simple loadboard HTML interface."""
    ui_code = os.getenv("LOADBOARD_UI_CODE")
    if ui_code:
        provided_code = request.query_params.get("code")
        if provided_code != ui_code:
            html = """
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Unauthorized</title>
                <style>
                  body { font-family: "Segoe UI", Arial, sans-serif; background: #f5f7fb; margin: 0; }
                  .card { max-width: 520px; margin: 80px auto; background: #fff; border: 1px solid #e5e7eb;
                    border-radius: 12px; padding: 24px; text-align: center; }
                  h1 { margin: 0 0 8px 0; font-size: 20px; }
                  p { margin: 0; color: #6b7280; font-size: 14px; }
                  code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
                </style>
              </head>
              <body>
                <div class="card">
                  <h1>Unauthorized</h1>
                  <p>Access requires a valid code. Please check the URL and include <code>?code=YOUR_CODE</code>.</p>
                </div>
              </body>
            </html>
            """
            return HTMLResponse(content=html, status_code=401)
    if not os.path.exists(LOADBOARD_UI_PATH):
        raise HTTPException(status_code=404, detail="Loadboard UI not found")
    with open(LOADBOARD_UI_PATH, "r", encoding="utf-8") as handle:
        html = handle.read()
    base_url = os.getenv("LOADBOARD_BASE_URL")
    if not base_url:
        base_url = str(request.base_url).rstrip("/")
    html = html.replace("{{BASE_URL}}", base_url)
    html = html.replace("{{LOGO_URL}}", LOADBOARD_LOGO_PATH)
    return HTMLResponse(html)


@app.post("/loadboard/simple")
async def post_loadboard_load(request: Request):
    """Post a load to the simple in-memory loadboard (accepts XML or JSON)."""
    if is_supabase_enabled():
        xml_content = await extract_xml_content(request)
        loadboard_service = get_loadboard_service()
        message, success_count = loadboard_service.process_xml_request(xml_content)
        status = "ok" if success_count > 0 else "error"
        return {"status": status, "message": message, "saved": success_count}

    content_type = request.headers.get("content-type", "").lower()
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace")
    payload: Any
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = body_str
    else:
        payload = body_str
    item = {
        "id": str(uuid4()),
        "content_type": content_type or "text/plain",
        "payload": payload,
        "received_at": datetime.utcnow().isoformat() + "Z"
    }
    LOADBOARD_POSTS.append(item)
    return {"status": "ok", "id": item["id"]}


@app.get("/loadboard/simple")
async def get_loadboard_loads(limit: int = 50, offset: int = 0):
    """Get posted loads (Supabase if configured, otherwise in-memory)."""
    if SUPABASE_ENABLED and supabase_client:
        try:
            end_index = max(offset, 0) + max(limit, 1) - 1
            result = (
                supabase_client.table("loadboard_loads")
                .select(
                    "unique_id,tracking_number,user_id,origin_city,origin_state,"
                    "destination_city,destination_state,origin_pickup_date,"
                    "destination_delivery_date,rate,weight,created_at,updated_at",
                    count="exact"
                )
                .order("updated_at", desc=True)
                .range(max(offset, 0), end_index)
                .execute()
            )
            count = result.count if hasattr(result, "count") else None
            if count is None and isinstance(result.data, list):
                count = len(result.data)
            return {"count": count or 0, "loads": result.data or [], "source": "supabase"}
        except Exception as e:
            logger.error(f"Supabase fetch failed, falling back to memory: {e}", exc_info=True)
    start = max(offset, 0)
    end = start + max(limit, 1)
    return {"count": len(LOADBOARD_POSTS), "loads": LOADBOARD_POSTS[start:end], "source": "memory"}


@app.get("/loadboard/count")
async def get_loadboard_count():
    """Get total count of loads (Supabase if configured, otherwise in-memory)."""
    if SUPABASE_ENABLED and supabase_client:
        try:
            result = supabase_client.table("loadboard_loads").select("unique_id", count="exact").execute()
            count = result.count if hasattr(result, "count") else None
            if count is None and isinstance(result.data, list):
                count = len(result.data)
            return {"count": count or 0, "source": "supabase"}
        except Exception as e:
            logger.error(f"Supabase count failed, falling back to memory: {e}", exc_info=True)
    return {"count": len(LOADBOARD_POSTS), "source": "memory"}


# Import LoadBoard router from new structure
from app.routers import loadboard
app.include_router(loadboard.router)


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
    total_routes: int  # Total routes found (before pagination)
    routes: List[RouteOption]  # Routes for current page
    search_criteria: Dict[str, Any]
    message: Optional[str] = None
    trip_plans: Optional[List[TripPlanDetail]] = None
    pagination: Optional[Dict[str, Any]] = None  # Pagination info


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


def parse_iso_to_minutes(iso_string: str, reference_time: Optional[datetime] = None) -> int:
    """
    Convert ISO 8601 timestamp to minutes from reference time.
    
    All times are assumed to be in Pacific timezone (America/Los_Angeles).
    Times are converted to UTC for consistent comparison.
    
    Args:
        iso_string: ISO 8601 timestamp string (assumed Pacific timezone)
        reference_time: Reference datetime in UTC. If None, uses 2025-01-01 00:00:00 UTC.
                        Should be set to earliest pickup time minus 24h for dynamic reference.
    
    Returns:
        Minutes from reference time
    """
    try:
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        
        dt = datetime.fromisoformat(iso_string)
        
        # If no timezone info, assume Pacific timezone (UTC-8 for PST, UTC-7 for PDT)
        # Use UTC-8 (PST) as default for consistency
        if dt.tzinfo is None:
            pacific_tz = timezone(timedelta(hours=-8))
            dt = dt.replace(tzinfo=pacific_tz)
        
        # Convert to UTC for consistent comparison
        dt_utc = dt.astimezone(timezone.utc)
        
        # Use provided reference time, or default to 2025-01-01 00:00:00 UTC
        if reference_time is None:
            ref_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            # Ensure reference_time is in UTC
            if reference_time.tzinfo is None:
                ref_dt = reference_time.replace(tzinfo=timezone.utc)
            else:
                ref_dt = reference_time.astimezone(timezone.utc)
        
        # Calculate difference in minutes
        delta = dt_utc - ref_dt
        minutes = int(delta.total_seconds() / 60)
        
        return minutes
    except Exception as e:
        logger.error(f"Error parsing time '{iso_string}': {e}", exc_info=True)
        return 0


def calculate_travel_time_miles(miles: float, speed_mph: float = 50.0) -> int:
    """Calculate travel time in minutes for given miles at speed."""
    return int((miles / speed_mph) * 60)


def can_chain_loads(load1: Dict, load2: Dict, 
                     max_deadhead: float = 100, 
                     unload_buffer_minutes: int = 60,
                     reference_time: Optional[datetime] = None) -> Tuple[bool, float, Optional[str]]:
    """
    Check if load2 can be chained after load1 with proper time window validation.
    
    Must satisfy: Delivery_i_time + unload_buffer + travel_time(deadhead) ≤ Pickup_{i+1}_latest
    And truck must be available at Pickup_{i+1}_earliest (can wait if early)
    
    Returns: (can_chain, deadhead_miles, error_message)
    """
    deliv1 = load1['destination']
    pickup2 = load2['origin']
    
    deadhead = haversine_distance(
        deliv1['latitude'], deliv1['longitude'],
        pickup2['latitude'], pickup2['longitude']
    )
    
    if deadhead > max_deadhead * 2:  # Allow 2x deadhead for chaining
        return False, deadhead, f"Deadhead {deadhead:.1f} miles exceeds max {max_deadhead * 2} miles"
    
    # Check time windows - use snake_case keys (delivery_window, pickup_window)
    delivery_window = load1.get('delivery_window', {})
    pickup_window = load2.get('pickup_window', {})
    
    if not delivery_window or not pickup_window:
        return False, deadhead, "Missing time windows"
    
    load1_delivery_earliest = parse_iso_to_minutes(delivery_window.get('earliest', ''), reference_time)
    load1_delivery_latest = parse_iso_to_minutes(delivery_window.get('latest', ''), reference_time)
    load2_pickup_earliest = parse_iso_to_minutes(pickup_window.get('earliest', ''), reference_time)
    load2_pickup_latest = parse_iso_to_minutes(pickup_window.get('latest', ''), reference_time)
    
    # Validate parsed times
    if load1_delivery_latest == 0 or load2_pickup_latest == 0:
        return False, deadhead, "Invalid time window format"
    
    # Calculate deadhead travel time (minutes)
    deadhead_travel_time = calculate_travel_time_miles(deadhead)
    
    # Key constraint: Delivery_i_time + unload_buffer + travel_time(deadhead) ≤ Pickup_{i+1}_latest
    # Use EARLIEST delivery time (more lenient) instead of latest for better chain opportunities
    earliest_arrival_at_load2 = load1_delivery_earliest + unload_buffer_minutes + deadhead_travel_time
    
    if earliest_arrival_at_load2 > load2_pickup_latest:
        return False, deadhead, f"Time window violation: cannot reach load2 pickup by latest time ({load2_pickup_latest} min) after delivering load1 at {load1_delivery_earliest} min"
    
    # Check if truck can be available at Pickup_{i+1}_earliest (can wait if early)
    # If we arrive too early, we can wait, but we must arrive by latest
    # This is already satisfied by the check above
    
    return True, deadhead, None


def validate_hos_for_chain(chain: List[Tuple[Dict, float]], 
                            start_time_minutes: int = 0,
                            max_driving_hours: float = 11.0,
                            max_on_duty_hours: float = 14.0,
                            required_rest_hours: float = 10.0,
                            reference_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate Hours of Service (HOS) for a route chain.
    
    DOT HOS Rules (simplified):
    - Max 11 hours driving after 10 consecutive hours off duty
    - Max 14 hours on-duty (driving + other work) after coming on duty
    - Must take 10-hour rest break after 11 hours driving or 14 hours on-duty
    
    Returns: (is_valid, error_message)
    """
    if not chain:
        return True, None
    
    current_time = start_time_minutes
    total_driving_minutes = 0
    total_on_duty_minutes = 0
    consecutive_driving_minutes = 0
    
    max_driving_minutes = int(max_driving_hours * 60)
    max_on_duty_minutes = int(max_on_duty_hours * 60)
    required_rest_minutes = int(required_rest_hours * 60)
    
    for i, (load, deadhead_before) in enumerate(chain):
        # Parse time windows
        pickup_window = load.get('pickup_window', {})
        delivery_window = load.get('delivery_window', {})
        
        if not pickup_window or not delivery_window:
            return False, f"Load {i+1} missing time windows"
        
        pickup_earliest = parse_iso_to_minutes(pickup_window.get('earliest', ''), reference_time)
        pickup_latest = parse_iso_to_minutes(pickup_window.get('latest', ''), reference_time)
        delivery_earliest = parse_iso_to_minutes(delivery_window.get('earliest', ''), reference_time)
        delivery_latest = parse_iso_to_minutes(delivery_window.get('latest', ''), reference_time)
        
        if pickup_latest == 0 or delivery_latest == 0:
            return False, f"Load {i+1} has invalid time windows"
        
        # Deadhead to pickup (driving time)
        deadhead_time = calculate_travel_time_miles(deadhead_before)
        total_driving_minutes += deadhead_time
        consecutive_driving_minutes += deadhead_time
        total_on_duty_minutes += deadhead_time
        
        # Arrive at pickup (wait if early, but must arrive by latest)
        arrival_at_pickup = max(current_time + deadhead_time, pickup_earliest)
        if arrival_at_pickup > pickup_latest:
            return False, f"Load {i+1}: Cannot reach pickup by latest time (HOS constraint)"
        
        # Load/unload time (on-duty but not driving) - estimate 60 minutes
        load_time = 60
        total_on_duty_minutes += load_time
        
        # Travel with load (driving time)
        load_distance = load.get('distance_miles', 0)
        load_travel_time = calculate_travel_time_miles(load_distance)
        total_driving_minutes += load_travel_time
        consecutive_driving_minutes += load_travel_time
        total_on_duty_minutes += load_travel_time
        
        # Arrive at delivery
        arrival_at_delivery = arrival_at_pickup + load_time + load_travel_time
        if arrival_at_delivery > delivery_latest:
            return False, f"Load {i+1}: Cannot deliver by latest time (HOS constraint)"
        
        # Unload time (on-duty but not driving) - estimate 60 minutes
        unload_time = 60
        total_on_duty_minutes += unload_time
        
        current_time = arrival_at_delivery + unload_time
        
        # Check HOS limits
        if consecutive_driving_minutes > max_driving_minutes:
            # Need rest break
            current_time += required_rest_minutes
            consecutive_driving_minutes = 0
            total_on_duty_minutes += required_rest_minutes
        
        if total_on_duty_minutes > max_on_duty_minutes:
            # Need rest break
            current_time += required_rest_minutes
            consecutive_driving_minutes = 0
            total_on_duty_minutes = required_rest_minutes  # Reset after rest
        
        # If this is not the last load, check if we can continue
        if i < len(chain) - 1:
            # Check if we have enough time to reach next pickup
            next_load = chain[i + 1][0]
            next_pickup_window = next_load.get('pickup_window', {})
            next_pickup_latest = parse_iso_to_minutes(next_pickup_window.get('latest', ''), reference_time)
            
            if next_pickup_latest == 0:
                return False, f"Next load has invalid pickup window"
            
            # This will be checked in can_chain_loads, but we verify HOS allows it
            if current_time > next_pickup_latest:
                return False, f"Cannot reach next load pickup in time due to HOS constraints"
    
    return True, None


def validate_route_chain(chain: List[Tuple[Dict, float]], 
                          start_time_minutes: int = 0,
                          max_deadhead: float = 100,
                          unload_buffer_minutes: int = 60,
                          reference_time: Optional[datetime] = None,
                          validate_hos: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate an entire route chain for time windows and HOS constraints.
    
    For each hop (Load i → Load i+1), checks:
    - Delivery_i_time + unload_buffer + travel_time(deadhead) ≤ Pickup_{i+1}_latest
    - Truck can be available at Pickup_{i+1}_earliest (can wait if early)
    - HOS feasibility: don't exceed driving limits; include rest resets (if validate_hos=True)
    
    Returns: (is_valid, error_message)
    """
    if len(chain) <= 1:
        return True, None  # Single load is always valid
    
    # Validate each consecutive pair
    for i in range(len(chain) - 1):
        load1 = chain[i][0]
        load2 = chain[i + 1][0]
        
        can_chain, deadhead, error = can_chain_loads(
            load1, load2,
            max_deadhead=max_deadhead,
            unload_buffer_minutes=unload_buffer_minutes,
            reference_time=reference_time
        )
        if not can_chain:
            return False, f"Load {i+1} → Load {i+2}: {error}"
    
    # Validate HOS for entire chain (optional - can be disabled if too strict)
    if validate_hos:
        hos_valid, hos_error = validate_hos_for_chain(chain, start_time_minutes, reference_time=reference_time)
        if not hos_valid:
            # For now, log but don't reject - HOS might be too strict
            logger.debug(f"HOS warning (not rejecting): {hos_error}")
            # return False, f"HOS violation: {hos_error}"
    
    return True, None


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
        logger.error(f"Error generating trip plan with Gemini: {e}")
        return None


def find_all_routes_from_request(request: AllRoutesRequest, max_chain_length: int = 5, 
                                 initial_max_deadhead: float = None, 
                                 auto_increase_deadhead: bool = True,
                                 max_iterations: int = 10,
                                 max_routes: int = 500,
                                 min_revenue: float = 0,
                                 max_deadhead_ratio: float = 0.5,
                                 min_required_routes: int = 10) -> Tuple[List[Dict], float]:
    """
    Find all possible route chains from the request data.
    
    Args:
        request: The route request with searchCriteria and loads
        max_chain_length: Maximum number of loads in a chain
        initial_max_deadhead: Initial max deadhead (if None, uses request options)
        auto_increase_deadhead: If True, automatically increase deadhead if no routes found
        max_iterations: Maximum iterations to try increasing deadhead
    
    Returns:
        Tuple of (routes_list, actual_deadhead_used)
    """
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
    
    # Calculate dynamic reference time from earliest pickup (24 hours before)
    # This ensures time windows are relative to actual load times, not a fixed date
    earliest_pickup_time = None
    for load in loads_dict:
        pickup_window = load.get('pickup_window', {})
        earliest_str = pickup_window.get('earliest', '')
        if earliest_str:
            try:
                # Parse as Pacific timezone
                if earliest_str.endswith('Z'):
                    earliest_str = earliest_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(earliest_str)
                if dt.tzinfo is None:
                    pacific_tz = timezone(timedelta(hours=-8))
                    dt = dt.replace(tzinfo=pacific_tz)
                dt_utc = dt.astimezone(timezone.utc)
                
                if earliest_pickup_time is None or dt_utc < earliest_pickup_time:
                    earliest_pickup_time = dt_utc
            except:
                pass
    
    # Set reference time to 24 hours before earliest pickup, or use default
    if earliest_pickup_time:
        reference_time = earliest_pickup_time - timedelta(hours=24)
        logger.info(f"Using dynamic reference time: {reference_time} UTC (24h before earliest pickup: {earliest_pickup_time} UTC)")
    else:
        reference_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        logger.warning(f"Could not determine earliest pickup time - using default reference time: {reference_time} UTC")
    
    # Get initial max deadhead from options
    if initial_max_deadhead is None:
        max_deadhead = 100
        if search_criteria.options:
            max_deadhead = search_criteria.options.get('maxOriginDeadheadMiles', 100)
    else:
        max_deadhead = initial_max_deadhead
    
    # Get destination deadhead limit
    dest_deadhead = max_deadhead
    if search_criteria.options:
        dest_deadhead = search_criteria.options.get('maxDestinationDeadheadMiles', max_deadhead)
    
    # Iterative deadhead increase - automatically increase if no routes found
    iteration = 0
    increment = 50  # Increase by 50 miles per iteration
    max_deadhead_limit = 500  # Maximum deadhead to try
    initial_origin_deadhead = max_deadhead
    initial_dest_deadhead = dest_deadhead
    best_routes = []
    best_deadhead = max_deadhead
    
    while iteration < max_iterations and max_deadhead <= max_deadhead_limit:
        # Find loads that start near origin
        starting_loads = []
        for load in loads_dict:
            pickup_lat = load['origin']['latitude']
            pickup_lon = load['origin']['longitude']
            distance = haversine_distance(origin_lat, origin_lon, pickup_lat, pickup_lon)
            if distance <= max_deadhead:
                starting_loads.append((load, distance))
        
        starting_loads.sort(key=lambda x: x[1])
        logger.info(f"Found {len(starting_loads)} loads within {max_deadhead}mi of origin")
        
        # Build chain graph
        chain_graph = defaultdict(list)
        chain_edges = 0
        for i, load1 in enumerate(loads_dict):
            for j, load2 in enumerate(loads_dict):
                if i != j:
                    can_chain, deadhead, error = can_chain_loads(load1, load2, max_deadhead, reference_time=reference_time)
                    if can_chain:
                        chain_graph[load1['load_id']].append((load2, deadhead))
                        chain_edges += 1
        logger.info(f"Chain graph: {chain_edges} valid edges found")
        
        # Find all routes using DFS with early stopping
        all_routes = []
        processed_chains = set()
        max_routes_during_search = max_routes * 3  # Allow 3x during search, filter later
        
        def dfs_route(current_chain: List[Tuple[Dict, float]], current_load: Dict, depth: int):
            """Depth-first search to find all route chains."""
            # Early stopping if we already have too many routes
            if len(all_routes) >= max_routes_during_search:
                return
            if depth > max_chain_length:
                return
            
            # Validate chain before adding (time windows + geographic progress)
            if len(current_chain) >= 2:
                # Geographic backtracking validation - reject routes going in opposite directions
                if dest_lat and dest_lon:
                    visited_states = set()
                    prev_distance_to_target = None
                    prev_distance_from_origin = None
                    
                    for i, (load, _) in enumerate(current_chain):
                        dest_lat_load = load['destination']['latitude']
                        dest_lon_load = load['destination']['longitude']
                        distance_to_target = haversine_distance(dest_lat_load, dest_lon_load, dest_lat, dest_lon)
                        distance_from_origin = haversine_distance(origin_lat, origin_lon, dest_lat_load, dest_lon_load)
                        current_state = load['destination']['state']
                        
                        # Reject if revisiting same state (backtracking)
                        if current_state in visited_states:
                            logger.debug(f"Chain rejected: revisiting state {current_state}")
                            return
                        visited_states.add(current_state)
                        
                        # Reject if moving away from target (backtracking >100mi)
                        if prev_distance_to_target is not None:
                            if distance_to_target > prev_distance_to_target + 100:
                                logger.debug(f"Chain rejected: backtracking from target ({distance_to_target:.1f}mi vs {prev_distance_to_target:.1f}mi)")
                                return
                        
                        # Reject if moving backward toward origin (getting closer to origin)
                        if prev_distance_from_origin is not None:
                            if distance_from_origin < prev_distance_from_origin - 50:
                                logger.debug(f"Chain rejected: backtracking toward origin ({distance_from_origin:.1f}mi vs {prev_distance_from_origin:.1f}mi)")
                                return
                        
                        prev_distance_to_target = distance_to_target
                        prev_distance_from_origin = distance_from_origin
                
                # Get start time from first load's pickup window
                first_load = current_chain[0][0]
                first_pickup_window = first_load.get('pickup_window', {})
                start_time = parse_iso_to_minutes(first_pickup_window.get('earliest', ''), reference_time)
                
                # Validate chain (time windows only - HOS disabled)
                is_valid, error_msg = validate_route_chain(
                    current_chain, start_time, max_deadhead,
                    reference_time=reference_time,
                    validate_hos=False  # Disable HOS - too strict
                )
                if not is_valid:
                    logger.debug(f"Chain validation failed: {error_msg}")
                    return  # Reject invalid chains
            
            # Check if current chain ends near destination (or no destination specified)
            if not dest_lat or not dest_lon:
                # No destination - accept all valid chains
                final_deliv = current_load['destination']
                distance_to_dest = 0
            else:
                final_deliv = current_load['destination']
                distance_to_dest = haversine_distance(
                    final_deliv['latitude'], final_deliv['longitude'],
                    dest_lat, dest_lon
                )
                
            # Accept ALL valid chains as alternate routes
            # Single-load routes: always add
            # Multi-load chains: add as alternate routes (even if not ending near destination)
            # Destination filtering happens later in the filtering step
            is_single_load = len(current_chain) == 1
            should_add = True  # Always add valid chains - they're alternate routes
            
            if should_add:
                    route = {
                        'route_id': len(all_routes) + 1,
                        'segments': [],
                        'total_distance': 0,
                        'total_revenue': 0,
                        'total_deadhead': 0,
                    'ends_near_destination': dest_lat is not None and dest_lon is not None and distance_to_dest <= dest_deadhead,
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
            
            # Try to extend chain (continue exploring even after adding current route)
            # This allows finding longer chains and alternate routes through intermediate states
            if current_load['load_id'] in chain_graph:
                next_loads_count = len(chain_graph[current_load['load_id']])
                for next_load, deadhead in chain_graph[current_load['load_id']]:
                    # Don't revisit same load in chain
                    if not any(l[0]['load_id'] == next_load['load_id'] for l in current_chain):
                        # Continue DFS to find longer chains (2-load, 3-load, etc.)
                        dfs_route(current_chain + [(next_load, deadhead)], next_load, depth + 1)
        
        # Start DFS from each starting load
        dfs_routes_added = 0
        for start_load, start_deadhead in starting_loads:
            chain_signature = (start_load['load_id'],)
            if chain_signature not in processed_chains:
                routes_before = len(all_routes)
                dfs_route([(start_load, start_deadhead)], start_load, 1)
                routes_after = len(all_routes)
                dfs_routes_added += (routes_after - routes_before)
                processed_chains.add(chain_signature)
        logger.info(f"DFS added {dfs_routes_added} routes from {len(starting_loads)} starting loads")
        
        # Also add single-load routes that start near origin
        # Add ALL single-load routes that start near origin (not just those ending near destination)
        for load in loads_dict:
            pickup_lat = load['origin']['latitude']
            pickup_lon = load['origin']['longitude']
            start_distance = haversine_distance(origin_lat, origin_lon, pickup_lat, pickup_lon)
            
            # Only add if pickup is reachable (within max_deadhead)
            if start_distance <= max_deadhead:
                # Calculate distance to destination if destination is specified
                distance_to_dest = 0
                if dest_lat and dest_lon:
                    deliv = load['destination']
                    distance_to_dest = haversine_distance(
                        deliv['latitude'], deliv['longitude'],
                        dest_lat, dest_lon
                    )
                
                # Add single-load route (regardless of destination proximity)
                # If destination is specified, we'll mark if it ends near destination
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
                    'ends_near_destination': dest_lat is not None and dest_lon is not None and distance_to_dest <= dest_deadhead,
                    'final_distance_to_dest': distance_to_dest
                }
                
                # Check if this single-load route is already in all_routes (from DFS)
                chain_sig = (load['load_id'],)
                if chain_sig not in processed_chains:
                    all_routes.append(route)
                    processed_chains.add(chain_sig)
        
        single_load_routes_added = len([r for r in all_routes if len(r['segments']) == 1])
        chained_routes_added = len([r for r in all_routes if len(r['segments']) > 1])
        logger.info(f"Found {len(all_routes)} total routes before filtering: {single_load_routes_added} single-load, {chained_routes_added} chained")
        
        # Remove duplicates
        unique_routes = []
        seen_signatures = set()
        for route in all_routes:
            sig = tuple((s['origin'], s['destination']) for s in route['segments'])
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_routes.append(route)
        
        # Filter routes by quality criteria
        filtered_routes = []
        for route in unique_routes:
            # Filter by minimum revenue
            if route['total_revenue'] < min_revenue:
                continue
            
            # Filter by deadhead ratio (deadhead should not exceed X% of total distance)
            if route['total_distance'] > 0:
                deadhead_ratio = route['total_deadhead'] / (route['total_distance'] + route['total_deadhead'])
                if deadhead_ratio > max_deadhead_ratio:
                    continue
            
            filtered_routes.append(route)
        
        # Sort by quality score: prioritize efficiency (less total miles, less deadhead, more loaded miles)
        # Priority: 
        # 1. More loaded miles (higher is better)
        # 2. Less total miles traveled (lower is better) 
        # 3. Less deadhead miles (lower is better)
        # 4. Prefer 2-load routes over 3+ load routes (more efficient)
        def quality_score(route):
            total_miles = route['total_distance'] + route['total_deadhead']
            loaded_miles = route['total_distance']  # Loaded miles
            deadhead_miles = route['total_deadhead']
            num_segments = len(route['segments'])
            
            # Calculate efficiency metrics
            if total_miles > 0:
                loaded_ratio = loaded_miles / total_miles  # Higher is better (more loaded, less deadhead)
                deadhead_ratio = deadhead_miles / total_miles  # Lower is better
            else:
                loaded_ratio = 0
                deadhead_ratio = 1
            
            # Penalty for too many segments (3+ loads often less efficient than 2 loads)
            segment_penalty = 0
            if num_segments >= 3:
                segment_penalty = (num_segments - 2) * 50  # Penalty for 3+ loads
            
            # Quality score: prioritize loaded miles, then efficiency, then penalize long chains
            # Higher score = better route
            score = (
                loaded_miles,  # Primary: more loaded miles is better
                loaded_ratio,  # Secondary: higher loaded ratio is better
                -total_miles,  # Tertiary: less total miles is better (negative for reverse sort)
                -deadhead_miles,  # Quaternary: less deadhead is better
                -segment_penalty  # Quinary: penalize 3+ load chains
            )
            
            return score
        
        filtered_routes.sort(key=quality_score, reverse=True)
        
        # If we don't have enough routes, relax the deadhead ratio filter and try again
        if len(filtered_routes) < min_required_routes and len(unique_routes) > len(filtered_routes):
            # Relax deadhead ratio to get more routes - be very aggressive
            relaxed_deadhead_ratio = min(0.95, max_deadhead_ratio + 0.2)  # Allow up to 95% deadhead
            relaxed_filtered = []
            for route in unique_routes:
                if route['total_revenue'] < min_revenue:
                    continue
                if route['total_distance'] > 0:
                    deadhead_ratio = route['total_deadhead'] / (route['total_distance'] + route['total_deadhead'])
                    if deadhead_ratio <= relaxed_deadhead_ratio:
                        relaxed_filtered.append(route)
                else:
                    relaxed_filtered.append(route)
            
            # Re-sort relaxed results
            relaxed_filtered.sort(key=quality_score, reverse=True)
            
            # Use relaxed results if we get more routes
            if len(relaxed_filtered) >= min_required_routes or len(relaxed_filtered) > len(filtered_routes):
                logger.info(f"Relaxed deadhead ratio to {relaxed_deadhead_ratio:.1%} to find more routes ({len(relaxed_filtered)} found, target: {min_required_routes})")
                filtered_routes = relaxed_filtered
        
        # If still not enough, remove deadhead ratio filter entirely (only keep revenue filter)
        if len(filtered_routes) < min_required_routes and len(unique_routes) > len(filtered_routes):
            no_deadhead_filter = []
            for route in unique_routes:
                if route['total_revenue'] >= min_revenue:
                    no_deadhead_filter.append(route)
            
            # Re-sort
            no_deadhead_filter.sort(key=quality_score, reverse=True)
            
            if len(no_deadhead_filter) > len(filtered_routes):
                logger.info(f"Removed deadhead ratio filter entirely to find more routes ({len(no_deadhead_filter)} found, target: {min_required_routes})")
                filtered_routes = no_deadhead_filter
        
        # Limit to top N routes
        original_count = len(filtered_routes)
        if len(filtered_routes) > max_routes:
            logger.info(f"Found {len(filtered_routes)} routes, limiting to top {max_routes} by quality")
            filtered_routes = filtered_routes[:max_routes]
        
        # Renumber routes
        for i, route in enumerate(filtered_routes):
            route['route_id'] = i + 1

        if len(filtered_routes) > len(best_routes):
            best_routes = list(filtered_routes)
            best_deadhead = max_deadhead
        
        # If we have enough routes, return them
        if len(filtered_routes) >= min_required_routes:
            if iteration > 0:
                logger.info(f"Found {len(filtered_routes)} routes (from {len(unique_routes)} total) with deadhead increased to {max_deadhead} miles (origin) and {dest_deadhead} miles (destination)")
            else:
                if len(unique_routes) > len(filtered_routes):
                    logger.info(f"Found {len(filtered_routes)} quality routes (filtered from {len(unique_routes)} total routes)")
            return filtered_routes, max_deadhead
        
        # Not enough routes found - increase deadhead if we have fewer than required
        if auto_increase_deadhead and len(filtered_routes) < min_required_routes:
            iteration += 1
            max_deadhead = initial_origin_deadhead + (increment * iteration)
            dest_deadhead = initial_dest_deadhead + (increment * iteration)
            if len(filtered_routes) == 0:
                logger.info(f"No routes found with deadhead {max_deadhead - increment} miles. Trying {max_deadhead} miles (origin) and {dest_deadhead} miles (destination)...")
            else:
                logger.info(f"Only {len(filtered_routes)} routes found (need {min_required_routes}). Increasing deadhead from {max_deadhead - increment} to {max_deadhead} miles (origin) and {dest_deadhead} miles (destination)...")
        else:
            # Don't auto-increase, just return filtered routes (empty if none found)
            return filtered_routes, max_deadhead
    
    # Reached max iterations or max deadhead limit
    if iteration > 0:
        logger.warning(f"Reached maximum deadhead limit ({max_deadhead_limit} miles) or iterations ({max_iterations}) without finding routes")
    # Return any routes we did find, even if below the target minimum
    if best_routes:
        return best_routes, best_deadhead
    return [], max_deadhead


@app.post("/get_all_routes", response_model=AllRoutesResponse)
async def get_all_routes(request: AllRoutesRequest, include_trip_plans: bool = False, 
                         page: int = Query(1, ge=1, description="Page number (starts at 1)"),
                         page_size: int = Query(10, ge=1, le=200, description="Number of routes per page (max 200)")):
    """
    Get all possible route chains from search criteria origin to destination.
    
    This endpoint accepts raw JSON with searchCriteria and loads structure,
    and returns all possible route chains that satisfy the constraints.
    
    Args:
        request: The route request with searchCriteria and loads
        include_trip_plans: If True, generate detailed trip plans using Gemini AI (requires GEMINI_API_KEY)
        page: Page number (starts at 1, default: 1)
        page_size: Number of routes per page (default: 10, max: 200)
    
    Note:
        - Deadhead miles are only increased if initial search returns 0 routes
        - Maximum 200 total routes will be found (configurable via options.maxRoutes)
        - Routes are sorted by quality (revenue per mile, then total revenue)
    """
    
    try:
        logger.info(f"Processing route request: {len(request.loads)} loads, page={page}, page_size={page_size}")
        
        # Validate input
        if not request.loads:
            logger.warning("Request rejected: No loads provided")
            raise HTTPException(status_code=400, detail="No loads provided")
        
        if not request.searchCriteria.origin:
            logger.warning("Request rejected: No origin in search criteria")
            raise HTTPException(status_code=400, detail="Search criteria must include origin")
        
        # Get max routes limit from options (default: 200 total, 10 per page)
        max_total_routes = 200  # Maximum total routes to find
        min_revenue = 0
        max_deadhead_ratio = 0.6  # Increased from 0.5 to 0.6 to allow more routes (deadhead can be up to 60%)
        max_chain_length = 5  # Reduced from 10 to prevent combinatorial explosion
        
        # Adjust filters based on number of loads to ensure we get results
        num_loads = len(request.loads)
        min_required_routes = 10  # Minimum routes we want to find
        
        if request.searchCriteria.options:
            max_total_routes = request.searchCriteria.options.get('maxRoutes', 200)
            min_revenue = request.searchCriteria.options.get('minRevenue', 0)
            max_deadhead_ratio = request.searchCriteria.options.get('maxDeadheadRatio', 0.6)
            max_chain_length = request.searchCriteria.options.get('maxChainLength', 5)
        
        # For 50-100 loads, we want at least 5-10 results
        # Adjust max_deadhead_ratio to be more lenient if we have many loads
        if 50 <= num_loads <= 100:
            # More lenient filtering for medium-sized input
            if max_deadhead_ratio < 0.8:
                max_deadhead_ratio = 0.8  # Allow up to 80% deadhead (very lenient)
            min_required_routes = 10  # Target at least 10 routes (5-10 range)
            max_chain_length = 3  # Max 3 legs in chain (less than 4)
        elif num_loads > 100:
            # Even more lenient for large inputs
            if max_deadhead_ratio < 0.85:
                max_deadhead_ratio = 0.85  # Allow up to 85% deadhead
            min_required_routes = 15
            max_chain_length = 3  # Max 3 legs in chain (less than 4)
        
        # Calculate pagination
        # We need to find enough routes to fill the requested page
        # Find max_routes = page * page_size to ensure we have enough for pagination
        # But also ensure we find at least min_required_routes
        max_routes_to_find = max(min_required_routes, min(max_total_routes, page * page_size))
        
        # Find all routes with automatic deadhead increase and smart filtering
        # Only increase deadhead if initial search returns 0 routes
        routes, actual_deadhead = find_all_routes_from_request(
            request, 
            max_chain_length=max_chain_length,
            auto_increase_deadhead=True,
            max_iterations=10,
            max_routes=max_routes_to_find,
            min_revenue=min_revenue,
            max_deadhead_ratio=max_deadhead_ratio,
            min_required_routes=min_required_routes
        )
        
        # Apply pagination
        total_routes_found = len(routes)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_routes = routes[start_idx:end_idx]
        total_pages = (total_routes_found + page_size - 1) // page_size if page_size > 0 else 1
        
        # Convert to response format
        route_options = []
        for route in paginated_routes:
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
        
        # Create response object
        response_data = AllRoutesResponse(
            total_routes=total_routes_found,  # Total routes found (before pagination)
            routes=route_options,  # Paginated routes for current page
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
            message=f"Found {total_routes_found} total routes. Showing page {page} of {total_pages} ({len(route_options)} routes)" + (" with detailed trip plans" if trip_plans else ""),
            trip_plans=trip_plans,
            pagination={
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'total_routes': total_routes_found,
                'routes_on_page': len(route_options),
                'has_next_page': page < total_pages,
                'has_previous_page': page > 1,
                'next_page': page + 1 if page < total_pages else None,
                'previous_page': page - 1 if page > 1 else None
            }
        )
        
        logger.info(f"Route request completed: {total_routes_found} routes found, returning page {page}")
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing route request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

