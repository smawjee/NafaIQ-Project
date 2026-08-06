# -*- coding: utf-8 -*-
"""Append a coverage-expansion section to the Execution Summary sheet."""
import re, shutil, zipfile
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
F = "../NafaIQ_Test_Cases_UPDATED.xlsx"

S_SECTION, S_HDR, S_KEY, S_VAL = 1, 1, 3, 4


def esc(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


SECTION = "2026-07-30 Coverage Expansion (added this pass)"
ROWS = [
    ("Field", "Value", "Interpretation"),
    ("New test cases added", "295",
     "56 appended to the 12 existing module sheets + 239 in 13 brand-new sheets."),
    ("Sheets", "14 -> 27",
     "New: Security & Authz, Market Analysis V4, Admin Dashboard, Market Data & Macro, Stock Detail, Monetary Desk, Localization & RTL, PWA & Resilience, Accessibility, Data Integrity, Cross-Module Flows, Performance & Session, AI Guardrails."),
    ("Manual/API cases total", "159 -> 454",
     "Excludes the 149 automated E2E journey executions, which are unchanged."),
    ("Executed live this pass", "21 executed: 18 Pass, 3 Fail",
     "Run on 2026-07-30 against a live local backend (127.0.0.1:8000, PROCESS_ROLE=web) using a real Supabase demo-user JWT. Every 'Pass' in a new sheet carries its observed evidence in the Actual Result column."),
    ("Remaining new cases", "274 Not Executed",
     "Authored and ready to run; they need a browser session, a second seeded account, an admin account, or a controlled failure injection."),
    ("Coverage gap that motivated this", "155 API endpoints vs ~40 previously covered",
     "The API surface was enumerated from the live OpenAPI schema. The admin subsystem (35 endpoints) and the V4-backed market analysis had zero cases before this pass."),
    ("Biggest untested blast radius", "DELETE /api/finance/{entity}",
     "A bulk-delete endpoint with no test coverage at all. See TC-DATA-20."),
]

DEFECT_SECTION = "New Defects Found While Executing (2026-07-30)"
DEFECTS = [
    ("Bug ID", "Area", "Test Case", "Observed Behaviour", "Severity", "Status"),
    ("NEW-BUG-01", "Zakat / Data Integrity", "TC-DATA-14",
     "The Zakat API trusts a client-supplied nisab_value_pkr with no validation. Posting nisab_value_pkr=0 with only PKR 1,000 of assets returned nisab_met=true. A crafted request can drive the calculation to any answer. The rate itself IS server-enforced at 2.5% (TC-DATA-15 passed), so this is specifically a nisab-source problem. Religiously sensitive - needs product/Shariah review.",
     "High", "Open"),
    ("NEW-BUG-02", "Market Analysis (V4)", "TC-MA-11",
     "GET /api/signals/v3/{symbol} returns a full analysis with NO Authorization header at all. If the market analysis is intended to be gated or metered, it is currently free to anyone who knows the URL.",
     "Medium", "Open - confirm intent"),
    ("NEW-BUG-03", "Security / Auth", "TC-SEC-02",
     "The invalid-token 401 leaks a Python codec detail: \"Invalid token: Invalid header string: 'utf-8' codec can't decode byte 0x8a in position 0: invalid start byte\". Access is correctly denied, but the message exposes implementation internals.",
     "Low", "Open"),
]

VERIFIED_GOOD = [
    ("Verified working", "Detail", ""),
    ("Server-side RBAC", "PASS",
     "A valid non-admin JWT was refused by /api/admin/overview, /users, /roles, /audit and /flags - all 403 'Admin access required'. Roles are resolved from the DB, not the token."),
    ("Ownership scoping (IDOR)", "PASS",
     "Holdings for portfolio ids 1, 3, 4, 999999 and -1 all returned 404 'Portfolio not found' for a user who owns only id 2."),
    ("Shared PSX token scope", "PASS",
     "PSX_API_TOKEN was refused as a user credential on both /api/portfolio/list and /api/admin/users."),
    ("Portfolio arithmetic", "PASS",
     "164,467 market value - 89,680 cost = 74,787 unrealised (83.39%) reconciles exactly; allocation 44.27 + 36.64 + 19.09 = 100.00."),
    ("Zakat clamping and boundary", "PASS",
     "Deductions exceeding assets clamp net_zakatable to 0; the nisab boundary is inclusive (180,000 liable / 179,999 not); negative assets are rejected 422."),
    ("Injection safety", "PASS",
     "A SQL-shaped symbol resolved to 'unavailable' with no SQL error - parameterisation holds."),
]


def row_xml(n, vals, style):
    cells = []
    for i, v in enumerate(vals):
        if v == "":
            continue
        col = chr(65 + i)
        cells.append(f'<c r="{col}{n}" s="{style}" t="inlineStr"><is><t>{esc(v)}</t></is></c>')
    return f'<row r="{n}" ht="30" customHeight="1">' + "".join(cells) + "</row>"


def main():
    zin = zipfile.ZipFile(F)
    parts = {n: zin.read(n) for n in zin.namelist()}
    zin.close()

    wb = ET.fromstring(parts["xl/workbook.xml"])
    rels = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    first = wb.find(f"{{{NS}}}sheets")[0]
    t = relmap[first.get(f"{{{RNS}}}id")]
    path = t[1:] if t.startswith("/") else ("xl/" + t if not t.startswith("xl/") else t)

    xml = parts[path].decode("utf-8")
    n = max(int(m) for m in re.findall(r'<row r="(\d+)"', xml))

    out = []
    n += 2
    out.append(row_xml(n, (SECTION,), S_SECTION))
    for r in ROWS:
        n += 1
        out.append(row_xml(n, r, S_HDR if r[0] == "Field" else S_VAL))
    n += 2
    out.append(row_xml(n, (DEFECT_SECTION,), S_SECTION))
    for r in DEFECTS:
        n += 1
        out.append(row_xml(n, r, S_HDR if r[0] == "Bug ID" else S_VAL))
    n += 2
    out.append(row_xml(n, ("Security & Correctness Checks That PASSED (2026-07-30)",), S_SECTION))
    for r in VERIFIED_GOOD:
        n += 1
        out.append(row_xml(n, r, S_HDR if r[0] == "Verified working" else S_VAL))

    xml = xml.replace("</sheetData>", "".join(out) + "</sheetData>")
    xml = re.sub(r'<dimension ref="A1:[A-Z]+\d+"/>', f'<dimension ref="A1:F{n}"/>', xml)
    parts[path] = xml.encode("utf-8")

    with zipfile.ZipFile(F, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in parts.items():
            z.writestr(k, v)
    print(f"Execution Summary extended to row {n}")


if __name__ == "__main__":
    main()
