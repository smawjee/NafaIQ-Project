# -*- coding: utf-8 -*-
"""Create a dedicated QA admin account and grant it super_admin.

Deliberately NOT the demo account: several test cases assert that the demo user
is refused by every admin endpoint, so making demo an admin would invalidate them.
Writes .qa-run/admin.json for the runners to pick up.
"""
import asyncio, json, sys, urllib.request, urllib.error

sys.path.insert(0, "../backend/src")


def env(p, k):
    for l in open(p, encoding="utf-8", errors="replace"):
        if l.strip().startswith(k + "="):
            return l.split("=", 1)[1].strip().strip('"')


S = env("../frontend/packages/web/.env", "VITE_SUPABASE_URL")
A = env("../frontend/packages/web/.env", "VITE_SUPABASE_ANON_KEY") or \
    env("../frontend/packages/web/.env", "VITE_SUPABASE_PUBLISHABLE_KEY")

EMAIL = "qa.admin.nafaiq@nafaiq.test"
PW = "QaAdmin!2026x"


def http(m, u, b=None, h=None):
    d = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(u, data=d, method=m)
    r.add_header("Content-Type", "application/json")
    for k, v in (h or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            return x.status, json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:300]


st, b = http("POST", f"{S}/auth/v1/signup", {"email": EMAIL, "password": PW}, {"apikey": A})
tok = b.get("access_token") if isinstance(b, dict) else None
if not tok:
    st, b = http("POST", f"{S}/auth/v1/token?grant_type=password",
                 {"email": EMAIL, "password": PW}, {"apikey": A})
    tok = b.get("access_token") if isinstance(b, dict) else None
if not tok:
    print("FAILED to obtain a session for the QA admin:", st, str(b)[:250])
    raise SystemExit(1)

import base64
payload = tok.split(".")[1]
payload += "=" * (-len(payload) % 4)
uid = json.loads(base64.urlsafe_b64decode(payload))["sub"]
print("QA admin user_id:", uid)


async def grant():
    from app.repositories.base import session
    from sqlalchemy import text
    async with session() as sess:
        existing = await sess.execute(
            text("SELECT role_slug FROM admin_role_assignments "
                 "WHERE user_id = :u AND revoked_at IS NULL"),
            {"u": uid},
        )
        have = [r[0] for r in existing.fetchall()]
        if "super_admin" not in have:
            await sess.execute(
                text("INSERT INTO admin_role_assignments (user_id, role_slug, granted_by, reason) "
                     "VALUES (:u, 'super_admin', :u, 'QA execution run 2026-07-30') "
                     "ON CONFLICT (user_id, role_slug) WHERE revoked_at IS NULL DO NOTHING"),
                {"u": uid},
            )
            await sess.commit()
        res = await sess.execute(
            text("SELECT role_slug FROM admin_role_assignments "
                 "WHERE user_id = :u AND revoked_at IS NULL"),
            {"u": uid},
        )
        return [r[0] for r in res.fetchall()]


roles = asyncio.run(grant())
print("roles now:", roles)
json.dump({"email": EMAIL, "password": PW, "user_id": uid, "roles": roles},
          open("admin.json", "w"), indent=1)
print("wrote admin.json")
