"""Excel jadvaldan bitta guruhning darslarini schedule.json ga chiqaradi.

Ishlatish:
    python extract_schedule.py TimeTable.xlsx 25-407

Jadval o'zgarganda shu skriptni qayta ishga tushirib, schedule.json ni yangilang.
"""
import json
import re
import sys

import openpyxl
from openpyxl.utils import get_column_letter

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOT_RE = re.compile(r"^\s*\d+\.\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})")


def day_columns(ws):
    """1-qatordagi kun nomlari va 2-qatordagi vaqt ustunlaridan {ustun: (kun, boshlanish, tugash)}."""
    starts = []
    for c in ws[1]:
        if c.value in DAYS:
            starts.append((c.column, DAYS.index(c.value)))
    starts.sort()
    cols = {}
    for col, day in starts:
        for cc in range(col, ws.max_column + 1):
            if cc != col and ws.cell(1, cc).value in DAYS:
                break
            m = SLOT_RE.match(str(ws.cell(2, cc).value or ""))
            if not m:
                break
            cols[cc] = (day, m.group(1), m.group(2))
    return cols


def blocks(ws):
    """Har 4 qatorli blok: (blok nomi, [qatorlar])."""
    r = 3
    while r <= ws.max_row:
        name = ws.cell(r, 1).value
        if name:
            yield str(name), r
            r += 4
        else:
            r += 1


def read_block(ws, top, cols, kind, match):
    out = []
    for cc, (day, start, end) in cols.items():
        subj = ws.cell(top, cc).value
        if not subj:
            continue
        groups = str(ws.cell(top + 3, cc).value or "")
        if not re.search(match, groups):
            continue
        out.append({
            "day": day,
            "start": start,
            "end": end,
            "subject": str(subj).strip(),
            "teacher": str(ws.cell(top + 1, cc).value or "").strip(),
            "room": str(ws.cell(top + 2, cc).value or "").strip(),
            "groups": [g.strip() for g in groups.split(",")],
            "source": kind,
        })
    return out


def main(path, group):
    wb = openpyxl.load_workbook(path, data_only=True)
    lessons = []
    for ws in wb:
        # faqat kun/vaqt sarlavhasi bor jadval varaqlari
        if ws.cell(1, 2).value not in DAYS and not any(c.value in DAYS for c in ws[1]):
            continue
        cols = day_columns(ws)
        if not cols:
            continue
        kind = "english" if "ingliz" in ws.title.lower() else "main"
        for _name, top in blocks(ws):
            lessons += read_block(ws, top, cols, kind, rf"(?<![\d-]){re.escape(group)}(?!\d)")
    # takrorlarni olib tashlash (bir xil kun+vaqt+fan)
    seen, uniq = set(), []
    for l in lessons:
        k = (l["day"], l["start"], l["subject"])
        if k not in seen:
            seen.add(k)
            uniq.append(l)
    uniq.sort(key=lambda l: (l["day"], l["start"]))
    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump({"group": group, "lessons": uniq}, f, ensure_ascii=False, indent=2)
    for l in uniq:
        print(f'{DAYS[l["day"]][:3]} {l["start"]}-{l["end"]}  {l["subject"]:<50} {l["teacher"]:<28} {l["room"]}')
    print(f"\nJami: {len(uniq)} ta dars")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
