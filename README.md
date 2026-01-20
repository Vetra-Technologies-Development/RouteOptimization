# Route Optimization API

FastAPI-based route optimization service for finding optimal trucking routes with load chaining.

## Features

- Route chain optimization with configurable deadhead limits
- Automatic deadhead adjustment when no routes are found
- Pagination support for large result sets
- Optional Gemini AI integration for detailed trip planning
- LoadBoard Network integration for receiving and storing loads
- Supabase integration for persistent load storage
- CORS enabled for frontend integration

## Installation

```bash
pip install -r requirements.txt
```

**Note:** OR-Tools (`ortools`) is optional and not included in the main requirements due to Python version compatibility. The `/solve_routes` endpoint will be unavailable without it. If you need OR-Tools and have a compatible Python version (3.8-3.13), install it separately:

```bash
pip install ortools
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

### Supabase Configuration (Required for LoadBoard Network)
- `SUPABASE_URL` (required): Your Supabase project URL (e.g., `https://your-project.supabase.co`)
- `SUPABASE_SERVICE_ROLE_KEY` (required): Your Supabase service role key from Settings > API > Service Role Key

**Note:** You'll need to create a `loads` table in Supabase with the following structure (or the endpoint will create it automatically on first use):
- `unique_id` (text, primary key): Combination of user_id and tracking_number
- `user_id` (text): LoadBoard Network user ID
- `tracking_number` (text): Load tracking number
- All other load fields as needed

### Manual Start

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST `/get_all_routes`

Find all possible route chains from origin to destination.

**Query Parameters:**
- `page` (int, default: 1): Page number
- `page_size` (int, default: 10): Number of routes per page (max 200)
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
New End Point - 3rd part integration
bash```
[Loadboard/dashboard - new end point](https://route-optimization-six.vercel.app/loadboard/dashboard)
```

## Deployment

### Vercel

This project is configured for Vercel deployment. See `scripts/vercel-deploy.md` for detailed deployment instructions.

**Quick Deploy:**
1. Push your code to GitHub
2. Import the repository in Vercel
3. Set environment variables (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, etc.)
4. Deploy

The `vercel.json` file is already configured with:
- Python 3.11 runtime
- 30-second function timeout
- Proper routing configuration



