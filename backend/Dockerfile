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

EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
