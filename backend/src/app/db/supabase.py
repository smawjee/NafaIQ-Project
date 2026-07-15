import asyncio

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


async def async_execute(query_fn):
    """Build + execute a supabase query in a thread with its own client.

    Each call creates a fresh client so there is zero shared mutable state
    (``supabase-py``'s ``httpx.Client`` is not documented as thread-safe).
    """
    def _run():
        client = create_client(settings.supabase_url, settings.supabase_service_key)
        return query_fn(client).execute()
    return await asyncio.to_thread(_run)


# PostgREST serves at most ~1000 rows per response (Supabase's default
# max-rows) however many a query asks for, and reports no error when it clips.
# Any read of a table that can exceed this MUST page.
PAGE_SIZE = 1000


async def select_all(table: str, columns: str, *, order_by: str, page_size: int = PAGE_SIZE) -> list[dict]:
    """Read every row of ``table``, paging past PostgREST's ~1000-row cap.

    ``order_by`` must name a unique column: paging is offset-based, so without a
    total order Postgres may return a row on two pages or on none.
    """
    rows: list[dict] = []
    offset = 0
    while True:
        res = await async_execute(
            lambda c, o=offset: c.table(table)
            .select(columns)
            .order(order_by)
            .range(o, o + page_size - 1)
        )
        page = res.data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size
