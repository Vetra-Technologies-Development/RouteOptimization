# Route Optimization API

FastAPI-based route optimization service for finding optimal trucking routes with load chaining.

## Features

- Route chain optimization with configurable deadhead limits
- Automatic deadhead adjustment when no routes are found
- Pagination support for large result sets
- Optional Gemini AI integration for detailed trip planning
- CORS enabled for frontend integration

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

### Logging Configuration
- `LOG_LEVEL` (default: `INFO`): Logging level - `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `LOG_FORMAT` (default: `text`): Log format - `text` or `json`
- `LOG_TO_FILE` (default: `false`): Enable file logging - `true` or `false`
- `LOG_FILE_PATH` (default: `api.log`): Path to log file (if `LOG_TO_FILE=true`)
- `LOG_API_REQUESTS` (default: `true`): Log all API requests and responses - `true` or `false`

### CORS Configuration
- `CORS_ORIGINS` (default: `*`): Comma-separated list of allowed origins, or `*` for all

### Optional Features
- `GEMINI_API_KEY` (optional): Google Gemini API key for trip planning features

See `.env.example` for a complete example configuration.

## Running Locally

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST `/get_all_routes`

Find all possible route chains from origin to destination.

**Query Parameters:**
- `page` (int, default: 1): Page number
- `page_size` (int, default: 50): Number of routes per page (max 200)
- `include_trip_plans` (bool, default: false): Generate detailed trip plans with Gemini AI

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
    },
    "options": {
      "maxOriginDeadheadMiles": 100,
      "maxDestinationDeadheadMiles": 100,
      "maxRoutes": 200,
      "maxChainLength": 3
    }
  },
  "loads": [...]
}
```

### POST `/solve_routes` (Optional - requires ortools)

Solve vehicle routing problem with time windows using OR-Tools.

## Deployment

### Vercel

This project is configured for Vercel deployment. Simply connect your repository to Vercel.

### Other Platforms

The API can be deployed to any platform that supports Python/FastAPI:
- Railway
- Render
- Heroku
- AWS Lambda (with Mangum)
- Google Cloud Run
- Azure Container Instances

