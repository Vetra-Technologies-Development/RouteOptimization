# Vercel Deployment Guide

This guide explains how to deploy the Route Optimization API to Vercel.

## Prerequisites

1. A Vercel account (sign up at https://vercel.com)
2. Vercel CLI installed (optional, for CLI deployment):
   ```bash
   npm i -g vercel
   ```

## Deployment Methods

### Method 1: GitHub Integration (Recommended)

1. Push your code to a GitHub repository
2. Go to https://vercel.com/new
3. Import your GitHub repository
4. Vercel will automatically detect the Python project
5. Configure environment variables (see below)
6. Click "Deploy"

### Method 2: Vercel CLI

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Login to Vercel:
   ```bash
   vercel login
   ```

3. Deploy:
   ```bash
   vercel
   ```

4. For production deployment:
   ```bash
   vercel --prod
   ```

## Environment Variables

Set the following environment variables in Vercel Dashboard (Settings > Environment Variables):

### Required for LoadBoard Network Integration
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Your Supabase service role key

### Optional
- `LOG_LEVEL` - Logging level (default: INFO)
- `LOG_FORMAT` - Log format: "text" or "json" (default: text)
- `LOG_TO_FILE` - Enable file logging: "true" or "false" (default: false)
- `LOG_FILE_PATH` - Path to log file (default: api.log)
- `LOG_API_REQUESTS` - Log API requests: "true" or "false" (default: true)
- `CORS_ORIGINS` - Comma-separated list of allowed origins, or "*" for all
- `GEMINI_API_KEY` - Google Gemini API key for trip planning features

## Project Structure

The project is configured to work with Vercel:
- `vercel.json` - Vercel configuration
- `runtime.txt` - Python version specification (3.11)
- `requirements.txt` - Python dependencies
- `main.py` - FastAPI application entry point

## API Endpoints

After deployment, your API will be available at:
- `https://your-project.vercel.app/`
- `https://your-project.vercel.app/docs` - API documentation
- `https://your-project.vercel.app/health` - Health check

## LoadBoard Network Endpoints

- `POST https://your-project.vercel.app/loadboard/post_loads` - Post loads
- `POST https://your-project.vercel.app/loadboard/remove_loads` - Remove loads

## Troubleshooting

### Build Failures

1. Check that all dependencies in `requirements.txt` are compatible with Python 3.11
2. Ensure `main.py` is in the root directory
3. Check Vercel build logs for specific errors

### Runtime Errors

1. Verify all environment variables are set correctly
2. Check function logs in Vercel Dashboard
3. Ensure Supabase credentials are valid

### Timeout Issues

- Default timeout is 30 seconds (configured in vercel.json)
- For longer operations, consider using background jobs or increasing timeout

## Local Testing

Before deploying, test locally:
```powershell
# Windows
.\scripts\start.ps1

# Linux/Mac
./scripts/start.sh
```

## Continuous Deployment

Vercel automatically deploys on every push to your main branch when connected via GitHub integration.

## Support

For Vercel-specific issues, refer to:
- Vercel Documentation: https://vercel.com/docs
- Python Runtime: https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python

