# -*- coding: utf-8 -*-
"""Merge the new NafaIQ test cases into NafaIQ_Test_Cases_.xlsx.

Surgical zip rewrite: existing sheet parts get new <row> elements appended and
their dimension/autoFilter/dataValidation refs widened; brand-new sheets are added
as new parts wired into workbook.xml, workbook.xml.rels and [Content_Types].xml.
Existing styling (style ids, frozen panes, tab colours) is preserved by reusing
the same style indices the original generator used.
"""
import re, shutil, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import cases_part1 as p1
import cases_part2 as p2
import cases_part3 as p3
import cases_part4 as p4

SRC = "../NafaIQ_Test_Cases_.xlsx"
BAK = "../NafaIQ_Test_Cases_.backup-2026-07-30.xlsx"
import os
OUT = os.environ.get("OUT_XLSX", "../NafaIQ_Test_Cases_UPDATED.xlsx")

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HDR = ["Test Case ID", "Module", "Test Scenario", "Preconditions", "Test Steps",
       "Test Data", "Expected Result", "Actual Result", "Status", "Priority"]
# style ids copied from the original generator's output (see sheet3.xml)
S_HDR, S_ID, S_SHORT, S_WRAP = 1, 2, 3, 4
COL_STYLE = [S_ID, S_SHORT, S_WRAP, S_WRAP, S_WRAP, S_WRAP, S_WRAP, S_WRAP, S_SHORT, S_SHORT]
WIDTHS = [13, 14, 26, 26, 40, 24, 34, 40, 12, 8]

NEW_SHEETS = [
    ("Security & Authz", p1.SECURITY),
    ("Market Analysis V4", p1.MARKET_ANALYSIS_V4),
    ("Admin Dashboard", p1.ADMIN),
    ("Market Data & Macro", p2.MARKET_DATA),
    ("Stock Detail", p2.STOCK_DETAIL),
    ("Monetary Desk", p2.MONETARY),
    ("Localization & RTL", p2.L10N),
    ("PWA & Resilience", p3.PWA),
    ("Accessibility", p3.A11Y),
    ("Data Integrity", p3.DATA),
    ("Cross-Module Flows", p3.FLOWS),
    ("Performance & Session", p3.PERF_SESSION),
    ("AI Guardrails", p3.AI_GUARD),
]


def esc(v):
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


VALID_STATUS = {"Not Executed", "Pass", "Fail", "Blocked", "Partial"}


def norm(r):
    """Every row must be exactly 10 columns. Rows authored without an explicit
    'Actual Result' carry 9 values - insert a blank Actual so Status/Priority
    do not shift a column to the left."""
    r = list(r)
    if len(r) == 9:
        r.insert(7, "")
    if len(r) != 10:
        raise ValueError(f"row has {len(r)} cols, expected 10: {r[0]!r}")
    if r[8] not in VALID_STATUS:
        raise ValueError(f"bad status {r[8]!r} in {r[0]!r}")
    if not re.fullmatch(r"P[1-4]", str(r[9])):
        raise ValueError(f"bad priority {r[9]!r} in {r[0]!r}")
    return r


def row_xml(rownum, values, header=False):
    ht = 24 if header else 62
    cells = []
    for i, v in enumerate(values):
        if v is None or v == "":
            continue
        st = S_HDR if header else COL_STYLE[i]
        cells.append(
            f'<c r="{col_letter(i)}{rownum}" s="{st}" t="inlineStr">'
            f"<is><t>{esc(v)}</t></is></c>"
        )
    return f'<row r="{rownum}" ht="{ht}" customHeight="1">' + "".join(cells) + "</row>"


def build_sheet(rows, tab_color="001F3864"):
    n = len(rows) + 1
    cols = "".join(
        f'<col width="{w}" customWidth="1" min="{i+1}" max="{i+1}"/>'
        for i, w in enumerate(WIDTHS)
    )
    body = row_xml(1, HDR, header=True)
    for idx, r in enumerate(rows, start=2):
        body += row_xml(idx, norm(r))
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}">'
        f'<sheetPr><tabColor rgb="{tab_color}"/><outlinePr summaryBelow="1" summaryRight="1"/>'
        f'<pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:J{n}"/>'
        f'<sheetViews><sheetView workbookViewId="0">'
        f'<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        f'<selection pane="bottomLeft" activeCell="A1" sqref="A1"/></sheetView></sheetViews>'
        f'<sheetFormatPr baseColWidth="8" defaultRowHeight="15"/>'
        f"<cols>{cols}</cols>"
        f"<sheetData>{body}</sheetData>"
        f'<autoFilter ref="A1:J{n}"/>'
        f'<dataValidations count="1"><dataValidation sqref="I2:I{n}" showDropDown="0" '
        f'showInputMessage="0" showErrorMessage="0" allowBlank="0" type="list">'
        f'<formula1>"Not Executed,Pass,Fail,Blocked"</formula1></dataValidation></dataValidations>'
        f'<pageMargins left="0.75" right="0.75" top="1" bottom="1" header="0.5" footer="0.5"/>'
        f'<pageSetup orientation="landscape" fitToHeight="0" fitToWidth="1"/></worksheet>'
    )


def main():
    shutil.copyfile(SRC, BAK)
    zin = zipfile.ZipFile(SRC)
    names = zin.namelist()
    parts = {n: zin.read(n) for n in names}
    zin.close()

    # --- map sheet name -> part path -------------------------------------
    wb = ET.fromstring(parts["xl/workbook.xml"])
    rels = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sheet_part = {}
    for sh in wb.find(f"{{{NS}}}sheets"):
        t = relmap[sh.get(f"{{{RNS}}}id")]
        t = t[1:] if t.startswith("/") else ("xl/" + t if not t.startswith("xl/") else t)
        sheet_part[sh.get("name")] = t

    appended = 0
    # --- append rows to existing sheets ----------------------------------
    for sname, rows in p4.APPEND.items():
        if sname not in sheet_part:
            print(f"  !! sheet not found, skipped: {sname}")
            continue
        path = sheet_part[sname]
        xml = parts[path].decode("utf-8")
        last = max(int(m) for m in re.findall(r'<row r="(\d+)"', xml))
        add = "".join(row_xml(last + 1 + i, norm(r)) for i, r in enumerate(rows))
        xml = xml.replace("</sheetData>", add + "</sheetData>")
        new_last = last + len(rows)
        xml = re.sub(r'<dimension ref="A1:J\d+"/>', f'<dimension ref="A1:J{new_last}"/>', xml)
        xml = re.sub(r'<autoFilter ref="A1:J\d+"/>', f'<autoFilter ref="A1:J{new_last}"/>', xml)
        xml = re.sub(r'sqref="I2:I\d+"', f'sqref="I2:I{new_last}"', xml)
        parts[path] = xml.encode("utf-8")
        appended += len(rows)
        print(f"  + {len(rows):>3} rows -> {sname}")

    # --- add new sheets ---------------------------------------------------
    existing_nums = [int(m.group(1)) for n in names
                     if (m := re.match(r"xl/worksheets/sheet(\d+)\.xml$", n))]
    next_num = max(existing_nums) + 1
    max_rid = max(int(r.get("Id")[3:]) for r in rels if r.get("Id").startswith("rId"))
    max_sheetid = max(int(sh.get("sheetId")) for sh in wb.find(f"{{{NS}}}sheets"))

    new_parts, new_rels, new_sheets_xml, new_ct = [], [], [], []
    added = 0
    for name, rows in NEW_SHEETS:
        if name in sheet_part:
            print(f"  !! sheet already exists, skipped: {name}")
            continue
        part = f"xl/worksheets/sheet{next_num}.xml"
        parts[part] = build_sheet(rows).encode("utf-8")
        max_rid += 1
        max_sheetid += 1
        new_rels.append(
            f'<Relationship Id="rId{max_rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{next_num}.xml"/>'
        )
        # the original generator declares xmlns:r on each <sheet>, not on the root
        new_sheets_xml.append(
            f'<sheet xmlns:r="{RNS}" name="{esc(name)}" sheetId="{max_sheetid}" '
            f'state="visible" r:id="rId{max_rid}"/>'
        )
        new_ct.append(
            f'<Override PartName="/{part}" ContentType="application/vnd.openxmlformats-'
            f'officedocument.spreadsheetml.worksheet+xml"/>'
        )
        next_num += 1
        added += len(rows)
        print(f"  + {len(rows):>3} rows -> NEW SHEET '{name}'")

    if new_sheets_xml:
        w = parts["xl/workbook.xml"].decode("utf-8")
        w = w.replace("</sheets>", "".join(new_sheets_xml) + "</sheets>")
        parts["xl/workbook.xml"] = w.encode("utf-8")

        r = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
        r = r.replace("</Relationships>", "".join(new_rels) + "</Relationships>")
        parts["xl/_rels/workbook.xml.rels"] = r.encode("utf-8")

        c = parts["[Content_Types].xml"].decode("utf-8")
        c = c.replace("</Types>", "".join(new_ct) + "</Types>")
        parts["[Content_Types].xml"] = c.encode("utf-8")

    order = list(parts.keys())
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order:
            z.writestr(n, parts[n])

    print(f"\nBackup written to {BAK}")
    print(f"Appended to existing sheets : {appended}")
    print(f"Added in new sheets         : {added}")
    print(f"TOTAL NEW TEST CASES        : {appended + added}")


if __name__ == "__main__":
    main()
