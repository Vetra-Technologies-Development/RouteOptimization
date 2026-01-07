"""Main FastAPI application."""
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routers import loadboard
from app.dependencies import is_supabase_enabled, is_gemini_enabled

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.LOG_FORMAT == "text" else None,
    handlers=[
        logging.StreamHandler(),
        *([logging.FileHandler(settings.LOG_FILE_PATH)] if settings.LOG_TO_FILE else [])
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Route Optimization API",
    description="Vehicle Routing Problem with Time Windows Solver and LoadBoard Network Integration",
    version="1.0.0"
)

# Add request/response logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    if settings.LOG_API_REQUESTS:
        start_time = datetime.now()
        logger.info(f"Request: {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    response = await call_next(request)
    
    if settings.LOG_API_REQUESTS:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if "*" not in settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(loadboard.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Route Optimization API",
        "version": "1.0.0",
        "endpoints": {
            "/loadboard/post_loads": "POST - LoadBoard Network post loads endpoint (receives XML, saves to Supabase)",
            "/loadboard/remove_loads": "POST - LoadBoard Network remove loads endpoint (receives XML, removes from Supabase)",
        },
        "features": {
            "supabase_enabled": is_supabase_enabled(),
            "gemini_enabled": is_gemini_enabled()
        }
    }

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

