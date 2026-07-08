from supabase import create_client, Client

from app.config import settings

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not settings.supabase_configured:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY "
                "(or the legacy SUPABASE_PUBLISHABLE_KEY / SUPABASE_SERVICE_ROLE_KEY)."
            )
        _supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    return _supabase
