FROM python:3.12-slim

WORKDIR /app

<<<<<<< HEAD
COPY pyproject.toml README.md ./
COPY src/ src/
=======
COPY . .

RUN pip install --no-cache-dir -e ".[dev]"
>>>>>>> usman

RUN pip install --no-cache-dir -e .

ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
