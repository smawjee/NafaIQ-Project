import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from panel import _fetch_ex_events, _to_panel, _fetch_rows  # noqa: E402


async def main():
    ev = await _fetch_ex_events()
    print("events:", len(ev))
    print(ev.head(5).to_string())
    print("dtypes:", ev.dtypes.to_dict())
    df = await _fetch_rows()
    p = _to_panel(df, ev)
    print("panel ex_cash non-zero:", int((p.ex_cash != 0).sum()))
    # manual spot check on first event
    if len(ev):
        e = ev.iloc[0]
        sym = str(e["symbol"])
        day = e["ex_date"]
        print(f"event[0]: sym={sym!r} day={day!r} type={type(day)}")
        print("  sym in cols:", sym in p.close.columns if hasattr(p.close, "columns") else "n/a")
        print("  day in index:", day in p.dates if hasattr(p.dates, "__contains__") else "n/a")
        if sym in p.close.columns and day in p.dates:
            i = p.dates.get_loc(day)
            j = list(p.close.columns).index(sym)
            print(f"  cell ({i},{j}): close={p.close[i, j]}")


if __name__ == "__main__":
    asyncio.run(main())
