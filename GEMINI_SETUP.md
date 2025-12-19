# Gemini AI Integration Setup

This project includes integration with Google's Gemini AI to generate detailed trip plans for all possible routes.

## Setup Instructions

### 1. Create Virtual Environment (Recommended)

**On macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `google-generativeai` and other required packages.

### 3. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy your API key

### 4. Set Environment Variable

**Linux/Mac:**

```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**Windows (CMD):**

```cmd
set GEMINI_API_KEY=your-api-key-here
```

**Or create a `.env` file:**

```bash
echo "GEMINI_API_KEY=your-api-key-here" > .env
```

Then install `python-dotenv` and the code will automatically load it.

### 5. Verify Setup

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

Check the root endpoint:

```bash
curl http://localhost:8000/
```

You should see `"gemini_enabled": true` if everything is set up correctly.

## Usage

### Using the API Endpoint

**Without trip plans (default):**

```bash
curl -X POST "http://localhost:8000/get_all_routes" \
  -H "Content-Type: application/json" \
  -d @boston-dallas-20.json
```

**With detailed trip plans:**

```bash
curl -X POST "http://localhost:8000/get_all_routes?include_trip_plans=true" \
  -H "Content-Type: application/json" \
  -d @boston-dallas-20.json
```

### Using the Example Script

**Basic usage:**

```bash
python3 example_get_all_routes.py boston-dallas-20.json
```

**With Gemini trip planning:**

```bash
python3 example_get_all_routes.py boston-dallas-20.json --with-plans
```

## What Gemini Provides

When `include_trip_plans=true`, Gemini AI generates:

1. **Route Summary**: Brief overview of the route
2. **Day-by-Day Itinerary**: Detailed schedule with estimated travel times
3. **Fuel Stops**: Recommended locations for refueling
4. **Rest Stops**: Recommended locations considering DOT hours of service
5. **Potential Issues**: Weather, traffic, road conditions warnings
6. **Optimization Tips**: Suggestions for improving the route
7. **Time Estimates**: Total driving and rest time needed

## Response Format

The response includes a `trip_plans` array with detailed information:

```json
{
  "trip_plans": [
    {
      "route_id": 1,
      "summary": "This route connects Boston to Dallas through...",
      "detailed_plan": "Full detailed trip plan text...",
      "estimated_duration_hours": 24.5,
      "recommendations": ["Tip 1", "Tip 2"],
      "potential_issues": ["Issue 1", "Issue 2"],
      "fuel_stops": ["Location 1", "Location 2"],
      "rest_stops": ["Location 1", "Location 2"]
    }
  ]
}
```

## Notes

- Trip plans are generated for the **top 5 routes** only (to avoid excessive API calls)
- Each Gemini API call may take 5-10 seconds
- Make sure you have sufficient API quota in your Google AI Studio account
- The API key is read from the `GEMINI_API_KEY` environment variable

## Troubleshooting

**"Gemini AI is not enabled" error:**

- Make sure `GEMINI_API_KEY` environment variable is set
- Restart the FastAPI server after setting the variable
- Check that `google-generativeai` package is installed

**API errors:**

- Verify your API key is correct
- Check your API quota in Google AI Studio
- Ensure you have internet connectivity
