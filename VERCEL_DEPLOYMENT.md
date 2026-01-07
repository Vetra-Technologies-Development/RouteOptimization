# Vercel Deployment Troubleshooting

## Common Issues and Solutions

### Issue 1: Supabase Installation Fails

**Problem:** `pyroaring` dependency requires C++ build tools

**Solution:** Vercel's build environment should have the necessary tools. If it still fails, the code will gracefully handle it as Supabase is optional.

### Issue 2: Build Timeout

**Solution:** The function timeout is set to 30 seconds in `vercel.json`. For longer operations, consider:
- Using background jobs
- Increasing timeout in Vercel dashboard
- Optimizing the code

### Issue 3: Import Errors

**Problem:** Module not found errors

**Solution:** 
- Ensure all dependencies are in `requirements.txt`
- Check that `main.py` is in the root directory
- Verify Python version is 3.11 (set in `vercel.json` and `runtime.txt`)

### Issue 4: Environment Variables Not Loading

**Solution:**
- Set environment variables in Vercel Dashboard (Settings > Environment Variables)
- Required: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `GEMINI_API_KEY`, `LOG_LEVEL`, `CORS_ORIGINS`, etc.

## Build Process

Vercel will:
1. Install Python 3.11
2. Run `pip install -r requirements.txt`
3. Build the function from `main.py`
4. Deploy to serverless functions

## Testing Deployment Locally

Use Vercel CLI to test locally:
```bash
npm i -g vercel
vercel dev
```

## Required Environment Variables

Set these in Vercel Dashboard:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Your Supabase service role key

## Optional Environment Variables

- `GEMINI_API_KEY` - For Gemini AI features
- `LOG_LEVEL` - Logging level (default: INFO)
- `CORS_ORIGINS` - CORS origins (default: *)

