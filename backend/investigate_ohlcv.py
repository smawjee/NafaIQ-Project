import os
import sys
from pathlib import Path

# Load .env manually (no python-dotenv dependency needed)
env_path = Path(__file__).resolve().parent / '.env'
if not env_path.exists():
    print(f"ERROR: .env not found at {env_path}")
    sys.exit(1)

with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip())

# Read connection params
host = os.getenv('SUPABASE_POOLER_HOST')
port = os.getenv('SUPABASE_POOLER_PORT', '6543')
user = os.getenv('SUPABASE_POOLER_USER')
password = os.getenv('SUPABASE_DATABASE_PASSWORD')
dbname = 'postgres'

missing = []
if not host: missing.append('SUPABASE_POOLER_HOST')
if not user: missing.append('SUPABASE_POOLER_USER')
if not password: missing.append('SUPABASE_DATABASE_PASSWORD')
if missing:
    print(f"ERROR: Missing env vars: {', '.join(missing)}")
    sys.exit(1)

print(f"Connecting to {user}@{host}:{port}/{dbname} (sslmode=require)")
print()

import psycopg2

conn = psycopg2.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    dbname=dbname,
    sslmode='require',
    connect_timeout=30,
)
conn.autocommit = True
cur = conn.cursor()

queries = [
    ("1. Bad row patterns",
     '''
     SELECT
       COUNT(*) FILTER (WHERE open < low) as open_below_low,
       COUNT(*) FILTER (WHERE high < close) as high_below_close,
       COUNT(*) FILTER (WHERE open < low OR high < close) as either_bad,
       COUNT(*) FILTER (WHERE open < low AND high < close) as both_bad,
       COUNT(*) as total_rows
     FROM psx_ohlcv;
     '''),

    ("2. Bad row percentage per symbol (top 20 worst offenders)",
     '''
     SELECT symbol,
       COUNT(*) as total_rows,
       COUNT(*) FILTER (WHERE open < low OR high < close) as bad_rows,
       ROUND(100.0 * COUNT(*) FILTER (WHERE open < low OR high < close) / COUNT(*), 2) as pct_bad
     FROM psx_ohlcv
     WHERE open < low OR high < close
     GROUP BY symbol
     ORDER BY pct_bad DESC
     LIMIT 20;
     '''),

    ("3. Date range of bad rows",
     '''
     SELECT MIN(date) as earliest_bad, MAX(date) as latest_bad
     FROM psx_ohlcv WHERE open < low OR high < close;
     '''),

    ("4. Sample bad rows (10) — show all columns",
     '''
     SELECT symbol, date, open, high, low, close, volume
     FROM psx_ohlcv WHERE open < low OR high < close LIMIT 10;
     '''),

    ("5. Check if bad rows correlate with split-adjusted rows",
     '''
     SELECT is_adjusted,
       COUNT(*) as total,
       COUNT(*) FILTER (WHERE open < low OR high < close) as bad,
       ROUND(100.0 * COUNT(*) FILTER (WHERE open < low OR high < close) / NULLIF(COUNT(*), 0), 2) as pct_bad
     FROM psx_ohlcv
     GROUP BY is_adjusted;
     '''),

    ("6. Symbols that are entirely bad",
     '''
     SELECT symbol, COUNT(*) as bad_rows
     FROM psx_ohlcv
     WHERE open < low OR high < close
     GROUP BY symbol
     HAVING COUNT(*) = COUNT(*) FILTER (WHERE open < low OR high < close)
     ORDER BY COUNT(*) DESC
     LIMIT 20;
     '''),

    ("7. Zero close or zero volume rows",
     '''
     SELECT
       COUNT(*) FILTER (WHERE close <= 0) as zero_close_rows,
       COUNT(*) FILTER (WHERE volume <= 0) as zero_volume_rows,
       COUNT(*) as total
     FROM psx_ohlcv;
     '''),

    ("8. Data source breakdown",
     '''
     SELECT
       CASE WHEN symbol LIKE 'PSX%%' THEN 'PSX'
            WHEN symbol IN ('KSE100','KSE30','KMI30','ALLSHR') THEN 'INDEX'
            ELSE 'STOCK'
       END as type,
       COUNT(*) as total,
       COUNT(*) FILTER (WHERE open < low OR high < close) as bad,
       ROUND(100.0 * COUNT(*) FILTER (WHERE open < low OR high < close) / COUNT(*), 2) as pct_bad
     FROM psx_ohlcv
     GROUP BY type
     ORDER BY pct_bad DESC;
     '''),
]

for title, sql in queries:
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        print("  " + " | ".join(str(c).ljust(18) for c in colnames))
        print("  " + "-" * (len(colnames) * 20))
        for row in rows:
            print("  " + " | ".join(str(v).ljust(18) if v is not None else "NULL".ljust(18) for v in row))
        print()
    except Exception as e:
        print(f"  ERROR: {e}")
        print()

cur.close()
conn.close()

print("Done.")
