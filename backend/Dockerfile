FROM python:3.12-slim

WORKDIR /app

# The build context is `backend/`, NOT the repo root — Railway's service Root
# Directory is set there. So this copies backend/* to /app, putting pyproject.toml
# at /app/pyproject.toml where the next step needs it.
#
# Do NOT "fix" this to `COPY backend/ .`: that path does not exist inside a
# backend/ context, so the copy resolves to nothing, /app has no pyproject.toml
# and the pip install below fails. That change is what broke the deploy of
# 2026-07-29 — it had never been built, because Railway only deploys `main` and
# it had only ever lived on `dev`.
COPY . .

RUN pip install --no-cache-dir -e ".[dev]"

ENV PORT=8000

# glibc gives each thread its own malloc arena and, once fragmented, effectively
# never returns those pages to the OS — RSS only ratchets up. This service leans
# on `asyncio.to_thread` (default executor: up to 32 threads), so it can hold 32
# fragmenting arenas on a 1 GB container. Capping the arena count trades a little
# allocator contention for a far flatter memory profile.
ENV MALLOC_ARENA_MAX=2

EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
