"""Dependency injection for services."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import optional dependencies
# Use a function to check availability at runtime, not just import time
def _check_supabase_available():
    """Check if supabase is available at runtime."""
    try:
        from supabase import create_client, Client
        return True, create_client, Client
    except ImportError:
        return False, None, None

# Initialize at module level, but can be refreshed
_SUPABASE_CHECK_RESULT = _check_supabase_available()
SUPABASE_AVAILABLE = _SUPABASE_CHECK_RESULT[0]
if SUPABASE_AVAILABLE:
    create_client = _SUPABASE_CHECK_RESULT[1]
    Client = _SUPABASE_CHECK_RESULT[2]
else:
    create_client = None
    Client = None

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from app.config.settings import settings
from app.services.supabase_service import SupabaseService
from app.services.loadboard_service import LoadBoardService


# Global service instances
_supabase_client: Optional[Client] = None
_supabase_service: Optional[SupabaseService] = None
_loadboard_service: Optional[LoadBoardService] = None


def get_supabase_client() -> Optional[Client]:
    """Get or create Supabase client."""
    global _supabase_client, SUPABASE_AVAILABLE, create_client, Client
    
    # Re-check availability at runtime in case package was installed after import
    if not SUPABASE_AVAILABLE:
        _SUPABASE_CHECK_RESULT = _check_supabase_available()
        SUPABASE_AVAILABLE = _SUPABASE_CHECK_RESULT[0]
        if SUPABASE_AVAILABLE:
            create_client = _SUPABASE_CHECK_RESULT[1]
            Client = _SUPABASE_CHECK_RESULT[2]
    
    if _supabase_client is not None:
        return _supabase_client
    
    if not SUPABASE_AVAILABLE:
        logger.warning("supabase not installed. LoadBoard Network integration will not be available.")
        return None
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.info("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables to enable LoadBoard Network integration")
        return None
    
    try:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        logger.info("Supabase client initialized successfully")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


def get_supabase_service() -> SupabaseService:
    """Get or create Supabase service."""
    global _supabase_service
    
    if _supabase_service is not None:
        return _supabase_service
    
    client = get_supabase_client()
    _supabase_service = SupabaseService(client)
    return _supabase_service


def get_loadboard_service() -> LoadBoardService:
    """Get or create LoadBoard service."""
    global _loadboard_service
    
    if _loadboard_service is not None:
        return _loadboard_service
    
    supabase_service = get_supabase_service()
    _loadboard_service = LoadBoardService(supabase_service)
    return _loadboard_service


def is_supabase_enabled() -> bool:
    """Check if Supabase is enabled."""
    global SUPABASE_AVAILABLE, create_client, Client
    
    # Re-check availability at runtime in case package was installed after import
    if not SUPABASE_AVAILABLE:
        _SUPABASE_CHECK_RESULT = _check_supabase_available()
        SUPABASE_AVAILABLE = _SUPABASE_CHECK_RESULT[0]
        if SUPABASE_AVAILABLE:
            create_client = _SUPABASE_CHECK_RESULT[1]
            Client = _SUPABASE_CHECK_RESULT[2]
    
    return bool(SUPABASE_AVAILABLE and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def is_gemini_enabled() -> bool:
    """Check if Gemini is enabled."""
    if not GEMINI_AVAILABLE:
        return False
    if not settings.GEMINI_API_KEY:
        return False
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        return True
    except:
        return False

