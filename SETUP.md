# Setup Instructions

## Quick Start

### 1. Create and Activate Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Gemini API Key (Optional, for trip planning)

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```bash
echo "GEMINI_API_KEY=your-api-key-here" > .env
```

Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### 4. Start the FastAPI Server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### 5. Test the API

```bash
# Check health
curl http://localhost:8000/health

# Get all routes (without trip plans)
python3 example_get_all_routes.py boston-dallas-20.json

# Get all routes with detailed trip plans
python3 example_get_all_routes.py boston-dallas-20.json --with-plans
```

## API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /solve_routes` - Solve VRPTW problem (OR-Tools)
- `POST /get_all_routes` - Get all possible route chains
- `POST /get_all_routes?include_trip_plans=true` - Get routes with Gemini AI trip plans

## Troubleshooting

**"externally-managed-environment" error:**
- Always use a virtual environment (see step 1)
- Never install packages globally on macOS

**Gemini API not working:**
- Make sure `GEMINI_API_KEY` is set
- Check that `google-generativeai` is installed
- Restart the server after setting the environment variable

**Import errors:**
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

