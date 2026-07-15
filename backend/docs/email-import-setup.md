# Bank-Email Import — Setup (Gmail API)

NafaIQ can read a user's Gmail, detect bank transaction-alert emails, and add
the transactions automatically. Access is a **read-only OAuth grant**
(`gmail.readonly`) — we never store a password, and the user can revoke access
at any time from their Google account.

This feature is **off unless configured**. It requires a Google OAuth client,
an encryption key, and the kill switch on.

---

## 1. Google Cloud setup (once)

At <https://console.cloud.google.com>:

1. **Create a project** → e.g. `NafaIQ`.
2. **APIs & Services → Library** → search **Gmail API** → **Enable**.
3. **APIs & Services → OAuth consent screen** → **External** → fill in app name,
   user support email, developer contact → Save.
   Leave publishing status = **Testing** (see the 7-day caveat below).
4. **Scopes → Add or remove scopes** → add
   `https://www.googleapis.com/auth/gmail.readonly`.
   Google flags it as a **restricted** scope — expected, and fine in Testing.
5. **Test users → Add users** → add **every Google account used in the demo**
   (up to 100).
   ⚠️ An account that is not on this list **cannot consent at all** — it gets a
   hard "access blocked" error, not a warning.
6. **Credentials → Create credentials → OAuth client ID → Web application**.
   Under **Authorized redirect URIs** add both:
   - `http://localhost:8000/api/integrations/gmail/callback` — local web dev
   - `https://<your-railway-app>.up.railway.app/api/integrations/gmail/callback` — mobile + prod
7. Copy the **Client ID** and **Client secret**.

### ⚠️ Mobile requires the deployed backend
Google only accepts `https://` or `http://localhost` redirect URIs — **never a
LAN IP** like `http://192.168.1.5:8000`. So Expo Go **cannot** complete OAuth
against a laptop backend. For mobile, deploy the backend and point
`EXPO_PUBLIC_API_URL` at the deployed URL.

---

## 2. Backend environment

```bash
# Kill switch — the poller won't run and /connect returns 503 unless true
EMAIL_IMPORT_ENABLED=true

# Fernet key: encrypts each user's Google refresh token at rest and signs the
# OAuth state. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Rotating it invalidates every stored grant (users must reconnect).
EMAIL_CRED_ENC_KEY=<generated key>

# From step 1.7
GOOGLE_CLIENT_ID=<...>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<...>

# Must EXACTLY match a redirect URI registered in the console
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/integrations/gmail/callback

# Where the callback sends a web user back to
WEB_APP_ORIGIN=http://localhost:3000

# Optional tuning
EMAIL_POLL_INTERVAL_MINUTES=5
EMAIL_IMPORT_MAX_LLM_PER_POLL=20
```

On **Railway**, set the same variables, with
`GOOGLE_OAUTH_REDIRECT_URI` and `WEB_APP_ORIGIN` pointing at the deployed URLs.

## 3. Apply the migration

`database/migrations/20260715100000_bank_email_import.sql` — adds
`user_email_integrations` and `user_transactions.email_message_id`.

**Restart the backend after applying it.** The transaction insert uses
SQLAlchemy reflection, so `email_message_id` is invisible until the process
re-reflects the schema on startup.

---

## ⚠️ The 7-day expiry (the thing that will bite you)

While the OAuth consent screen is in **Testing**, Google expires refresh tokens
after **7 days**. The importer will simply stop, and the user must reconnect.

- The app handles this deliberately: the failing sync marks the connection
  `enabled = false` with `last_error`, and Settings shows a **Reconnect Gmail**
  button instead of failing silently.
- **Before any demo: reconnect Gmail that morning.** A connection made a week
  earlier will be dead.

Removing the expiry means **publishing** the app, which for a restricted scope
requires a **CASA security assessment** — annual, paid, several weeks. Not
worth it for a demo.

### Production paths (when this outgrows testing)
1. **Publish + CASA audit** — keeps this exact architecture; costs money/time.
2. **Forwarding-address ingest** — user forwards bank alerts to a NafaIQ
   address; no Google verification at all, and a much smaller privacy surface.
   Only the fetch layer (`services/email_import/gmail_client.py`) would change;
   the parsers, dedup, and notification path are provider-agnostic.

---

## How it works

1. **Connect** — `GET /api/integrations/gmail/connect?platform=web|mobile`
   returns a Google consent URL. The user consents; Google redirects to
   `/api/integrations/gmail/callback`, which is public but authenticated by a
   signed, 10-minute `state` (Fernet) that binds the code to a user. The backend
   exchanges the code and stores the **encrypted refresh token**.
2. **Poll** — `job_poll_inboxes` (every `EMAIL_POLL_INTERVAL_MINUTES`, 24/7 —
   not market-gated) mints an access token per user and queries Gmail with a
   **server-side filter**: `(from:hbl.com OR from:meezanbank.com OR …) after:<watermark>`.
   Non-bank mail is never downloaded.
3. **Parse** — deterministic per-bank templates first (`rules.py`: free, exact);
   Gemini/Groq JSON fallback only for unrecognised formats (`llm.py`), capped by
   `EMAIL_IMPORT_MAX_LLM_PER_POLL`. OTPs, statements, promos and **declined**
   transactions are excluded before any parsing.
4. **Import** — inserted into `user_transactions` with `source='bank_email'` and
   `email_message_id` (the Gmail message id). A **partial unique index** on
   `(user_id, email_message_id)` makes re-polling idempotent.
5. **Notify** — reuses `notify_activity`, so the user gets the in-app + email
   receipt ("Auto-added from your bank email…") and can edit/remove it.

### Adding a bank
Add the sender domain to `BANK_SENDER_DOMAINS` in
`services/email_import/senders.py` (it feeds the Gmail query), and — optionally
— a template to `rules.py`. Without a template the LLM fallback still handles
it; the template just makes it free and exact.

### Categories must stay lowercase
Budgets are lowercased on write and joined to transactions by a
**case-sensitive** string compare. `ParsedTransaction` enforces this, and
anything unrecognised falls back to `other`. A capitalised category would
silently fail to move the user's budget.
