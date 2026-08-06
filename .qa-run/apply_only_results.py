# -*- coding: utf-8 -*-
"""Write executed statuses/evidence into the workbook, matching by Test Case ID.
Does not add rows - purely a status update pass."""
import json, re, shutil, zipfile
import xml.etree.ElementTree as ET

from update_workbook import row_xml, col_letter, NS, RNS

F = "../NafaIQ_Test_Cases_.xlsx"
RESULTS = json.load(open("results.json"))


def main():
    shutil.copyfile(F, "../NafaIQ_Test_Cases_.prev.xlsx")
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

    updated, seen = 0, set()
    for sname, path in sheet_part.items():
        if sname in ("Execution Summary", "E2E Journey Results"):
            continue
        xml = parts[path].decode("utf-8")
        root = ET.fromstring(xml)
        out, changed = [], False
        for row in root.find(f"{{{NS}}}sheetData").findall(f"{{{NS}}}row"):
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
                out.append(row_xml(int(row.get("r")), [cells.get(col_letter(i), "") for i in range(10)]))
                updated += 1
                seen.add(tc)
                changed = True
            else:
                out.append(None)
        if changed:
            src = re.findall(r"<row [^>]*>.*?</row>", xml, re.S)
            assert len(src) == len(out), f"{sname}: row drift"
            body = re.search(r"<sheetData>.*?</sheetData>", xml, re.S).group(0)
            xml = xml.replace(body, "<sheetData>" + "".join(o or s for o, s in zip(out, src)) + "</sheetData>")
            parts[path] = xml.encode("utf-8")

    with zipfile.ZipFile(F, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in parts.items():
            z.writestr(k, v)

    missing = sorted(set(RESULTS) - seen)
    print(f"rows updated: {updated}")
    if missing:
        print(f"ids not found in sheet ({len(missing)}): {missing}")


if __name__ == "__main__":
    main()
