# Email Notifications — Production Setup

The email-notification feature is fully implemented in code. Delivery works out
of the box in **test mode** (Resend only sends to the Resend account owner's own
address). To send to **any** user's email — every account created on the app —
you must verify a domain in Resend. **No code changes are required**; this is
Resend configuration plus environment variables.

## The one requirement

Verifying a domain in Resend lifts the test-mode "owner only" restriction. That
is the entire change needed to email all users.

## 1. Decide which Resend account is "production"

Pick **one** account everyone shares — ideally a team/company Resend account,
not a personal one, so delivery doesn't depend on any single person. Whatever
account you verify the domain on is the account whose API key must go into
production.

## 2. Verify a domain you control

- In that account: **Resend → Domains → Add Domain**, enter a domain you own
  (e.g. `nafaiq.app`).
- Resend gives you a set of **DNS records** (SPF, DKIM, usually DMARC).
- Add those records wherever the domain's DNS is managed (registrar, Cloudflare,
  Vercel DNS, …), then click **Verify**. Propagation is usually minutes.

> ⚠️ **Catch:** you can only verify a domain you have DNS access to. The app is
> hosted at `nafaiq.vercel.app` — confirm you actually own `nafaiq.app`. If not,
> register it, or verify a different domain you do own and send from that
> (e.g. `alerts@yourdomain.com`).

## 3. Point the from-address at that domain

Once verified, set:

```
RESEND_FROM_EMAIL=alerts@<your-verified-domain>
```

Switch it **off** `onboarding@resend.dev` — that test sender is permanently
owner-only no matter what.

## 4. Set it on Railway, not just locally

All users hit the **deployed backend on Railway**, not a local machine, so local
`.env` changes don't affect them. In the **Railway dashboard → your service →
Variables**, set:

```
RESEND_API_KEY=<the production account's key>
RESEND_FROM_EMAIL=alerts@<your-verified-domain>
```

Railway redeploys on a variable change. After that, every account on the app —
web or mobile — receives emails, from your branded sender, to any address.

## Summary

1. Choose the production Resend account (team-owned ideally).
2. Verify a domain you control (add the DNS records Resend gives you).
3. Set `RESEND_FROM_EMAIL` to an address on that verified domain.
4. Put `RESEND_API_KEY` + `RESEND_FROM_EMAIL` in **Railway's** environment.

That is the entire "make it work for everyone" change; the code is already done.

## Notes

- `RESEND_API_KEY` / `RESEND_FROM_EMAIL` live in `.env` files, which are
  gitignored — nothing secret is committed. The committed default sender in
  `app/config.py` is `alerts@nafaiq.app`.
- The activity/receipt emails (`email_activity`) are opt-in per user (default
  off); threshold alerts and watchlist big-move alerts use `email_alerts`
  (default on). Both are toggled in the app's Settings → Notifications.
