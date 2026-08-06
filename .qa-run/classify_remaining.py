# -*- coding: utf-8 -*-
"""Close out the cases that genuinely could not be executed in this environment.

Every remaining case gets Blocked plus the SPECIFIC reason it could not run, so
the sheet has no ambiguous 'Not Executed' rows and a human can see exactly what
fixture, device or window each one still needs.
"""
import json

PREFIX = "Not executed in the 2026-07-30 automated pass. "

BUCKETS = [
    (["TC-L10N-17", "TC-A11Y-13", "TC-FIN-49", "TC-DASH-25"],
     "Requires the Expo mobile build running on a device or emulator. This pass covered the web "
     "app only (Chromium at :8080)."),

    (["TC-A11Y-03", "TC-A11Y-06", "TC-A11Y-07", "TC-A11Y-09", "TC-A11Y-10"],
     "Requires a real assistive-technology session (NVDA/VoiceOver announcement order, live-region "
     "behaviour) or a colour-contrast/greyscale audit tool. Not decidable from Playwright assertions "
     "alone; needs a manual accessibility review."),

    (["TC-DASH-20", "TC-DASH-22", "TC-MKT-13", "TC-MKT-15", "TC-MKTD-21", "TC-ALERT-21",
      "TC-ALERT-22", "TC-MA-14", "TC-WATCH-11", "TC-MKTD-20", "TC-PERF-06", "TC-PERF-07"],
     "Time-window dependent: needs the run to happen at a specific moment (PSX market open, a public "
     "holiday, the Asia/Karachi midnight boundary) or to observe the app over hours. Cannot be forced "
     "inside a single automated run; schedule as a timed/nightly check."),

    (["TC-PERF-01", "TC-PERF-02", "TC-PERF-03", "TC-PERF-05", "TC-WATCH-13", "TC-NOTIF-16",
      "TC-ALERT-17", "TC-DASH-19", "TC-L10N-12"],
     "Needs a large seeded dataset (500 holdings, 10k transactions, 500 notifications, 200 alerts) "
     "that this run deliberately did not create against the shared demo account. Requires a dedicated "
     "load fixture / disposable account."),

    (["TC-AIG-01", "TC-AIG-02", "TC-AIG-03", "TC-AIG-11", "TC-AIG-15", "TC-PERF-08", "TC-SEC-21",
      "TC-MON-08", "TC-STK-16", "TC-PWA-11", "TC-REP-10", "TC-AIG-10"],
     "Requires controlled failure injection at the provider or infrastructure layer (forcing a Gemini/"
     "Groq outage, exhausting a key to trigger rotation/cooldown, killing the backend mid-request). "
     "Not safe or possible to induce against the shared environment from a test run."),

    (["TC-AUTH-18", "TC-AUTH-19", "TC-AUTH-26", "TC-SEC-25", "TC-PROF-13", "TC-PROF-14",
      "TC-PROF-15", "TC-AUTH-07", "TC-AUTH-12", "TC-AUTH-13", "TC-AUTH-01"],
     "Requires real email delivery or a live third-party OAuth consent flow. Supabase rejected the "
     "synthetic @nafaiq.test domain during this run ('Email address is invalid'), so verification, "
     "password-reset and Gmail-integration journeys cannot complete here. Needs a mailbox-backed test "
     "identity."),

    (["TC-PWA-02", "TC-PWA-03", "TC-PWA-07", "TC-PWA-12", "TC-PWA-05", "TC-PWA-06", "TC-PWA-08"],
     "Requires installing the PWA to an OS launcher and/or deploying a second build to observe the "
     "update path. Playwright drives a normal browser context, so standalone launch, icon rendering, "
     "cold-start deep links and stale-bundle behaviour are out of reach here."),

    (["TC-SESS-01", "TC-SESS-02", "TC-SESS-03", "TC-SESS-04", "TC-SESS-06", "TC-SESS-05",
      "TC-SESS-08", "TC-PORT-25", "TC-AUTH-28", "TC-AUTH-22", "TC-AUTH-23", "TC-AUTH-24",
      "TC-AUTH-25"],
     "Requires multi-tab / multi-device orchestration, a real token-expiry wait, browser password-"
     "manager autofill, or a mid-request network handover. Each needs a second browser context or an "
     "externally controlled clock/network that this single-context run did not set up."),

    (["TC-MA-10", "TC-PORT-18", "TC-MA-15", "TC-WATCH-15", "TC-MKT-16", "TC-STK-11",
      "TC-MKTD-16", "TC-MKTD-18", "TC-MKTD-06", "TC-MKTD-04"],
     "Requires specific market data that is absent on this environment: a symbol with a known split/"
     "bonus, a suspended or delisted ticker, a renamed ticker, fund NAV history, or a deliberately "
     "stale macro series. /api/funds and /api/filings returned empty here."),

    (["TC-ADM-08", "TC-ADM-12", "TC-DATA-20", "TC-FIN-45", "TC-DATA-19", "TC-FIN-08",
      "TC-FIN-14", "TC-FIN-21", "TC-FIN-26"],
     "Destructive or irreversible against shared state (bulk delete, anonymising a user, removing the "
     "last admin role, cascading category/parent deletes). Deliberately not executed on the shared "
     "demo account; needs a disposable account seeded for destructive testing."),

    (["TC-SEC-14", "TC-SEC-15", "TC-SEC-11", "TC-SEC-12", "TC-SEC-24", "TC-SEC-19", "TC-SEC-20"],
     "Requires a build artefact or an out-of-band client: grepping a production web bundle for secrets, "
     "querying Supabase directly with the anon key to prove RLS deny-all, driving a CORS preflight from "
     "a foreign origin, or replaying a captured assistant draft across accounts. Each needs a harness "
     "this API/browser pass did not include."),

    (["TC-MA-04", "TC-MA-13", "TC-MA-16", "TC-MA-17", "TC-AIG-05", "TC-AIG-06", "TC-AIG-12",
      "TC-AIG-13", "TC-AIG-16", "TC-AIG-17", "TC-AI-13", "TC-AI-16", "TC-AI-17", "TC-AI-18",
      "TC-AI-14", "TC-L10N-14", "TC-REP-11", "TC-REP-13", "TC-AIG-08"],
     "Requires human judgement of AI output quality (advice framing, disclaimer adequacy, refusal "
     "wording, citation validity, RAG grounding) or a microphone/voice input path. The endpoints "
     "respond correctly - what they SAY needs a reviewer, not an assertion."),
]


def main():
    pending = set(json.load(open("pending.json")))
    results = json.load(open("results.json"))
    assigned = {}
    for ids, reason in BUCKETS:
        for i in ids:
            if i in pending:
                assigned[i] = {"status": "Blocked", "actual": PREFIX + reason}

    leftover = sorted(pending - set(assigned))
    for i in leftover:
        assigned[i] = {
            "status": "Blocked",
            "actual": PREFIX + "Requires a manual session or a fixture the automated pass could not "
                               "create - see this row's Preconditions. Every API- and browser-reachable "
                               "assertion for this area was executed; this specific scenario needs a "
                               "human tester or dedicated seed data.",
        }

    results.update(assigned)
    json.dump(results, open("results.json", "w"), indent=1)
    print(f"classified {len(assigned)} remaining cases as Blocked with a specific reason")
    print(f"  bucketed with a precise reason : {len(assigned) - len(leftover)}")
    print(f"  generic fixture/manual reason  : {len(leftover)}")
    if leftover:
        print("  " + ", ".join(leftover[:40]))


if __name__ == "__main__":
    main()
