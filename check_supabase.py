"""Quick script to check Supabase configuration."""
from app.dependencies import SUPABASE_AVAILABLE, is_supabase_enabled
from app.config.settings import settings

print("=== Supabase Status ===")
print(f"SUPABASE_AVAILABLE: {SUPABASE_AVAILABLE}")
print(f"SUPABASE_URL: {settings.SUPABASE_URL}")
print(f"SUPABASE_SERVICE_ROLE_KEY: {'SET' if settings.SUPABASE_SERVICE_ROLE_KEY else 'NOT SET'}")
print(f"is_supabase_enabled(): {is_supabase_enabled()}")

if SUPABASE_AVAILABLE:
    try:
        from supabase import create_client
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        print("SUCCESS: Supabase client created successfully!")
    except Exception as e:
        print(f"ERROR: Error creating client: {e}")
else:
    print("✗ Supabase package not available")

