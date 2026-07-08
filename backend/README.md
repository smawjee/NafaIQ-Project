# NafaIQ PSX API

Python FastAPI microservice for PSX market data. Scrapes DPS, polls AhleTrade, caches in Supabase.

```bash
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```
