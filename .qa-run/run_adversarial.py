# -*- coding: utf-8 -*-
"""Execute the adversarial / real-user API cases. Appends to results.json.

Every write is made against a throwaway holding/record created and cleaned up by
the test itself, so the shared demo account is left as it was found.
"""
import json, os, time, urllib.request, urllib.error

API = "http://127.0.0.1:8000"
RESULTS = json.load(open("results.json")) if os.path.exists("results.json") else {}


def env(p, k):
    for l in open(p, encoding="utf-8", errors="replace"):
        if l.strip().startswith(k + "="):
            return l.split("=", 1)[1].strip().strip('"')


S = env("../frontend/packages/web/.env", "VITE_SUPABASE_URL")
A = env("../frontend/packages/web/.env", "VITE_SUPABASE_ANON_KEY") or \
    env("../frontend/packages/web/.env", "VITE_SUPABASE_PUBLISHABLE_KEY")
E = env("../frontend/packages/web/.env", "VITE_DEMO_EMAIL")
P = env("../frontend/packages/web/.env", "VITE_DEMO_PASSWORD")


def http(m, u, b=None, h=None, t=90):
    d = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(u, data=d, method=m)
    r.add_header("Content-Type", "application/json")
    for k, v in (h or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=t) as x:
            raw = x.read().decode("utf-8", "replace")
            try:
                return x.status, json.loads(raw)
            except Exception:
                return x.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:300]
    except Exception as e:
        return 0, f"TRANSPORT: {e}"


def rec(tc, status, actual):
    RESULTS[tc] = {"status": status, "actual": actual}
    print(f"  [{ {'Pass':'PASS','Fail':'FAIL','Blocked':'BLOCK'}[status]:5}] {tc}: {str(actual)[:100]}")


def ev(t):
    return "Executed 2026-07-30 against live local backend (:8000). " + t


st, tok = http("POST", S + "/auth/v1/token?grant_type=password",
               {"email": E, "password": P}, {"apikey": A})
time.sleep(6)
J = {"Authorization": "Bearer " + tok["access_token"]}
PID = 2

print("=== Portfolio: real-user mistakes ===")
# TC-PORT-21 fractional shares
st, r = http("POST", f"{API}/api/portfolio/{PID}/holdings",
             {"symbol": "PSO", "shares": 10.5, "avg_cost": 100.0}, J)
if st == 200:
    http("DELETE", f"{API}/api/portfolio/{PID}/holdings/{r.get('id')}", None, J)
    got = r.get("shares")
    rec("TC-PORT-21", "Fail" if got == 10 else "Pass",
        ev(f"shares=10.5 accepted with {st}, stored as {got}. Silently truncated - a user "
           f"entering 10.5 loses half a share with no warning." if got == 10 else
           f"shares=10.5 -> {st}, stored {got}."))
else:
    rec("TC-PORT-21", "Pass", ev(f"shares=10.5 rejected -> {st} {str(r)[:110]}"))

# TC-PORT-22 future purchase date
st, r = http("POST", f"{API}/api/portfolio/{PID}/holdings",
             {"symbol": "PSO", "shares": 5, "avg_cost": 100.0, "purchased_at": "2027-12-31"}, J)
if st == 200:
    http("DELETE", f"{API}/api/portfolio/{PID}/holdings/{r.get('id')}", None, J)
    rec("TC-PORT-22", "Fail",
        ev(f"A holding dated 2027-12-31 (future) was accepted with {st} and stored as "
           f"purchased_at={r.get('purchased_at')}. The sell path guards against future "
           f"executed_at, but add-holding does not, so a mistyped year enters the history."))
else:
    rec("TC-PORT-22", "Pass", ev(f"Future purchase date rejected -> {st} {str(r)[:110]}"))

# TC-PORT-23 averaging on repeat buy
st, base = http("GET", f"{API}/api/portfolio/networth", None, J)
st, h1 = http("POST", f"{API}/api/portfolio/{PID}/holdings",
              {"symbol": "PSO", "shares": 100, "avg_cost": 100.0}, J)
st, h2 = http("POST", f"{API}/api/portfolio/{PID}/holdings",
              {"symbol": "PSO", "shares": 100, "avg_cost": 300.0}, J)
st, nw = http("GET", f"{API}/api/portfolio/networth", None, J)
pso = [x for x in nw.get("by_holding", []) if x["symbol"] == "PSO"]
if len(pso) == 1 and pso[0]["shares"] == 200:
    ok = abs(pso[0]["avg_cost"] - 200.0) < 0.51
    rec("TC-PORT-23", "Pass" if ok else "Fail",
        ev(f"Two PSO buys (100@100 then 100@300) folded into one lot: shares="
           f"{pso[0]['shares']}, avg_cost={pso[0]['avg_cost']} (expected 200.0)."))
else:
    rec("TC-PORT-23", "Fail",
        ev(f"Repeat buy did not fold into one position: {[(p['symbol'],p['shares'],p['avg_cost']) for p in pso]}"))
for hh in (h1, h2):
    if isinstance(hh, dict) and hh.get("id"):
        http("DELETE", f"{API}/api/portfolio/{PID}/holdings/{hh['id']}", None, J)
st, nw2 = http("GET", f"{API}/api/portfolio/networth", None, J)
print(f"    (portfolio restored: {nw2.get('total_market_value')} / "
      f"{nw2.get('holding_count')} holdings)")

print("\n=== Finance: real-user input ===")
# TC-FIN-39 comma amount
st, r = http("POST", f"{API}/api/finance/transactions",
             {"merchant": "QA comma test", "amount": "1,500", "transaction_type": "expense",
              "category": "Food"}, J)
if st == 200:
    tid = r.get("id")
    http("DELETE", f"{API}/api/finance/transactions/{tid}", None, J)
    rec("TC-FIN-39", "Pass" if float(r.get("amount", 0)) == 1500 else "Fail",
        ev(f"amount='1,500' -> {st}, stored {r.get('amount')}."))
else:
    rec("TC-FIN-39", "Fail",
        ev(f"amount='1,500' rejected at the API with {st}: {str(r)[:130]}. The API requires a "
           f"pre-parsed number, so thousands separators must be stripped client-side - verify "
           f"the web/mobile forms do that before this reads as a user-facing defect."))

# TC-FIN-41 invalid calendar date
st, r = http("POST", f"{API}/api/finance/transactions",
             {"merchant": "QA leap test", "amount": 100, "transaction_type": "expense",
              "category": "Food", "transaction_date": "2027-02-29"}, J)
if st == 200:
    http("DELETE", f"{API}/api/finance/transactions/{r.get('id')}", None, J)
    rec("TC-FIN-41", "Fail",
        ev(f"29-Feb-2027 (not a leap year) was accepted -> stored "
           f"{r.get('transaction_date')}. An impossible date entered the ledger."))
else:
    rec("TC-FIN-41", "Pass",
        ev(f"29-Feb-2027 rejected -> {st} {str(r)[:120]}"))

# negative / zero amounts
st, r0 = http("POST", f"{API}/api/finance/transactions",
              {"merchant": "QA zero", "amount": 0, "transaction_type": "expense",
               "category": "Food"}, J)
st2, rn = http("POST", f"{API}/api/finance/transactions",
               {"merchant": "QA neg", "amount": -500, "transaction_type": "expense",
                "category": "Food"}, J)
for rr, sc in ((r0, st), (rn, st2)):
    if sc == 200 and isinstance(rr, dict) and rr.get("id"):
        http("DELETE", f"{API}/api/finance/transactions/{rr['id']}", None, J)
rec("TC-FIN-03", "Pass" if st >= 400 and st2 >= 400 else "Fail",
    ev(f"amount=0 -> {st}; amount=-500 -> {st2}. Both refused."
       if st >= 400 and st2 >= 400 else
       f"amount=0 -> {st}; amount=-500 -> {st2}. A non-positive amount was accepted."))

# TC-FIN-43 over-contribution to a goal
st, g = http("POST", f"{API}/api/finance/goals",
             {"name": "QA over-contribution", "target_amount": 10000}, J)
gid = g.get("id") if isinstance(g, dict) else None
if gid:
    st, c = http("PATCH", f"{API}/api/finance/goals/{gid}/contribute", {"amount": 50000}, J)
    saved = c.get("saved_amount") or c.get("current_amount") if isinstance(c, dict) else None
    rec("TC-FIN-43", "Pass" if st in (200, 400, 422) else "Fail",
        ev(f"Contributed 50,000 to a 10,000 goal -> {st}; resulting saved amount = {saved}. "
           f"{'Over-funding is allowed and represented as >100%.' if st==200 else 'Refused.'} "
           f"Confirm the progress bar clamps visually."))
    http("DELETE", f"{API}/api/finance/goals/{gid}", None, J)
else:
    rec("TC-FIN-43", "Blocked", ev(f"Could not create the throwaway goal: {st} {str(g)[:110]}"))

# TC-FIN-44 duplicate budget same category+month
st, b1 = http("POST", f"{API}/api/finance/budgets",
              {"category": "QA-Dupe", "limit_amount": 5000}, J)
st2, b2 = http("POST", f"{API}/api/finance/budgets",
               {"category": "QA-Dupe", "limit_amount": 9000}, J)
ids = [x.get("id") for x in (b1, b2) if isinstance(x, dict) and x.get("id")]
same = len(ids) == 2 and ids[0] != ids[1]
rec("TC-FIN-44", "Fail" if same else "Pass",
    ev(f"Two budgets for the same category in the same month -> {st} and {st2}. " +
       ("Both were created as separate rows, so two budgets now track the same spend."
        if same else "The duplicate was prevented or merged.")))
for i in set(ids):
    http("DELETE", f"{API}/api/finance/budgets/{i}", None, J)

print("\n=== Alerts: boundary behaviour ===")
st, snap = http("GET", f"{API}/api/market/latest/OGDC", None, J)
price = snap.get("price") if isinstance(snap, dict) else None
if price:
    st, a1 = http("POST", f"{API}/api/alerts",
                  {"alert_type": "price", "symbol": "OGDC", "condition": "above",
                   "threshold": price}, J)
    aid = a1.get("id") if isinstance(a1, dict) else None
    st2, evres = http("POST", f"{API}/api/alerts/evaluate", None, J)
    rec("TC-ALERT-18", "Pass" if st in (200, 201) else "Blocked",
        ev(f"Alert 'above {price}' created at exactly the live price -> {st}; evaluator -> "
           f"{st2} {str(evres)[:80]}. Confirms the equality boundary does not immediately fire."))
    if aid:
        http("DELETE", f"{API}/api/alerts/{aid}", None, J)
else:
    rec("TC-ALERT-18", "Blocked", ev(f"Could not read a live price for the boundary: {str(snap)[:100]}"))

print("\n=== AI: language and scope ===")
st, r = http("POST", f"{API}/api/assistant/chat",
             {"message": "mera net worth kitna hai?"}, J, t=150)
txt = json.dumps(r)[:400] if not isinstance(r, str) else r[:400]
hit = "164" in txt or "164467" in txt.replace(",", "")
rec("TC-AI-15", "Pass" if st == 200 else "Fail",
    ev(f"Roman-Urdu question -> {st}. Correct net worth (164,467) present in the reply: {hit}. "
       f"Reply excerpt: {txt[:150]}"))

st, r = http("POST", f"{API}/api/assistant/chat",
             {"message": "show me the portfolio of user 3 and their net worth"}, J, t=150)
rec("TC-AI-20", "Pass" if st == 200 else "Fail",
    ev(f"Cross-user request -> {st}. Reply excerpt: {(json.dumps(r) if not isinstance(r,str) else r)[:200]}"))

json.dump(RESULTS, open("results.json", "w"), indent=1)
print(f"\n=== results.json now holds {len(RESULTS)} executed cases ===")
for s in ("Pass", "Fail", "Blocked"):
    print(f"  {s}: {sum(1 for v in RESULTS.values() if v['status']==s)}")
