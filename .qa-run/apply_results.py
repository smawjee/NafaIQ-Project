# -*- coding: utf-8 -*-
"""Append the part-5 adversarial cases and write executed statuses/evidence
back into the workbook, matching rows by Test Case ID."""
import json, re, shutil, zipfile
import xml.etree.ElementTree as ET

import cases_part5 as p5
from update_workbook import esc, norm, row_xml, col_letter, NS, RNS, COL_STYLE

F = "../NafaIQ_Test_Cases_.xlsx"
BAK = "../NafaIQ_Test_Cases_.pre-execution-backup.xlsx"
RESULTS = json.load(open("results.json"))


def main():
    shutil.copyfile(F, BAK)
    zin = zipfile.ZipFile(F)
    parts = {n: zin.read(n) for n in zin.namelist()}
    zin.close()

    wb = ET.fromstring(parts["xl/workbook.xml"])
    rels = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    sheet_part = {}
    for sh in wb.find(f"{{{NS}}}sheets"):
        t = relmap[sh.get(f"{{{RNS}}}id")]
        t = t[1:] if t.startswith("/") else ("xl/" + t if not t.startswith("xl/") else t)
        sheet_part[sh.get("name")] = t

    # ---- 1. append the part-5 adversarial rows -------------------------
    added = 0
    for sname, rows in p5.APPEND5.items():
        if sname not in sheet_part:
            print(f"  !! missing sheet {sname}")
            continue
        path = sheet_part[sname]
        xml = parts[path].decode("utf-8")
        last = max(int(m) for m in re.findall(r'<row r="(\d+)"', xml))
        add = "".join(row_xml(last + 1 + i, norm(r)) for i, r in enumerate(rows))
        xml = xml.replace("</sheetData>", add + "</sheetData>")
        n = last + len(rows)
        xml = re.sub(r'<dimension ref="A1:J\d+"/>', f'<dimension ref="A1:J{n}"/>', xml)
        xml = re.sub(r'<autoFilter ref="A1:J\d+"/>', f'<autoFilter ref="A1:J{n}"/>', xml)
        xml = re.sub(r'sqref="I2:I\d+"', f'sqref="I2:I{n}"', xml)
        parts[path] = xml.encode("utf-8")
        added += len(rows)
        print(f"  + {len(rows):>2} adversarial rows -> {sname}")

    # ---- 2. write statuses + evidence back by Test Case ID -------------
    updated, seen = 0, set()
    for sname, path in sheet_part.items():
        if sname in ("Execution Summary", "E2E Journey Results"):
            continue
        xml = parts[path].decode("utf-8")
        root = ET.fromstring(xml)
        out = []
        changed = False
        for row in root.find(f"{{{NS}}}sheetData").findall(f"{{{NS}}}row"):
            rn = row.get("r")
            cells = {}
            for c in row.findall(f"{{{NS}}}c"):
                col = (c.get("r") or "").rstrip("0123456789")
                el = c.find(f"{{{NS}}}is")
                cells[col] = "".join(t.text or "" for t in el.iter(f"{{{NS}}}t")) if el is not None else ""
            tc = cells.get("A", "")
            if tc in RESULTS:
                res = RESULTS[tc]
                cells["H"] = res["actual"]
                cells["I"] = res["status"]
                vals = [cells.get(col_letter(i), "") for i in range(10)]
                out.append(row_xml(int(rn), vals))
                updated += 1
                seen.add(tc)
                changed = True
            else:
                out.append(None)
        if changed:
            # rebuild only the rows we replaced, leaving the rest byte-identical
            src_rows = re.findall(r"<row [^>]*>.*?</row>", xml, re.S)
            assert len(src_rows) == len(out), f"{sname}: row count drift"
            new_rows = "".join(o if o else s for o, s in zip(out, src_rows))
            body = re.search(r"<sheetData>.*?</sheetData>", xml, re.S).group(0)
            xml = xml.replace(body, f"<sheetData>{new_rows}</sheetData>")
            parts[path] = xml.encode("utf-8")

    with zipfile.ZipFile(F, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in parts.items():
            z.writestr(k, v)

    missing = sorted(set(RESULTS) - seen)
    print(f"\nadversarial rows added : {added}")
    print(f"rows updated with results: {updated}")
    if missing:
        print(f"result ids not found in the sheet ({len(missing)}): {missing}")


if __name__ == "__main__":
    main()
