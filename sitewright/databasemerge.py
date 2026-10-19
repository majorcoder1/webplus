"""Database Merge: a table of records (names, prices, photos...) and a repeating area that shows
one design once for every record. The page is built from the records when the site is published."""
import copy
import csv
import io
import math
import os
import re

from .model import new_id

TEXT_KEYS = ("text", "label", "link", "alt", "caption", "url", "title", "code", "address", "tip", "pop_text")
TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
PICTURES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def new_database(name="Database", fields=None):
    return dict(id=new_id(), name=name, fields=list(fields or ["name", "description"]), rows=[])


def find(doc, dbid):
    return next((d for d in getattr(doc, "databases", []) if d["id"] == dbid), None)


def clean_field(name):
    return re.sub(r"[^A-Za-z0-9_]+", "_", name.strip()).strip("_") or "field"


def sorted_rows(db, field="", descending=False, limit=0):
    rows = list(db["rows"])
    if field and field in db["fields"]:
        def key(r):
            v = str(r.get(field, ""))
            try:
                return (0, float(v), "")
            except ValueError:
                return (1, 0.0, v.lower())
        rows.sort(key=key, reverse=bool(descending))
    return rows[:limit] if limit and limit > 0 else rows


def merge_text(text, row):
    return TOKEN.sub(lambda m: str(row.get(m.group(1), "")), text)


def merge_item(doc, t, row):
    for k in TEXT_KEYS:
        if isinstance(t.get(k), str) and "{{" in t[k]:
            t[k] = merge_text(t[k], row)
    if t.get("kind") == "table":
        t["cells"] = [[merge_text(c, row) if isinstance(c, str) else c for c in line] for line in t.get("cells", [])]
    f = t.get("field")
    if f and t.get("kind") == "image":
        val = str(row.get(f, ""))
        if val in doc.assets:
            t["asset"], t["srcurl"] = val, ""
        elif val:
            t["asset"], t["srcurl"] = "", val
        else:
            t["asset"], t["srcurl"], t["hidden_empty"] = "", "", True


def expand(doc, page, items):
    """The items and page the way they look once every repeating area has been filled in."""
    reps = [i for i in page["items"] if i.get("kind") == "repeater"]
    if not reps:
        return items, page
    items = copy.deepcopy(items)
    page = dict(page)
    for rep0 in sorted(reps, key=lambda r: r["y"]):
        rep = next((i for i in items if i["id"] == rep0["id"]), None)
        if rep is None:
            continue
        db = find(doc, rep.get("db"))
        rows = sorted_rows(db, rep.get("sort", ""), rep.get("desc"), rep.get("limit", 0)) if db else []
        tmpl = [i for i in items if i.get("rep") == rep["id"]]
        w, h, gap = rep["w"], rep["h"], rep.get("gap", 16)
        cols = max(int(rep.get("cols", 1)), 1)
        nrows = int(math.ceil(len(rows) / float(cols)))
        total = nrows * h + max(nrows - 1, 0) * gap
        extra = total - h
        bottom = rep["y"] + h
        new = []
        for n, row in enumerate(rows):
            dx, dy = (n % cols) * (w + gap), (n // cols) * (h + gap)
            for t in tmpl:
                c = copy.deepcopy(t)
                c["id"] = "%s_r%d" % (t["id"], n)
                c["x"] += dx
                c["y"] += dy
                c.pop("rep", None)
                if n and c.get("ident"):
                    c["ident"] = "%s-%d" % (c["ident"], n + 1)
                merge_item(doc, c, row)
                if not c.pop("hidden_empty", False):
                    new.append(c)
        pos = items.index(rep)
        drop = {id(rep)} | {id(t) for t in tmpl}
        out = []
        for i, it in enumerate(items):
            if i == pos:
                out.extend(new)
            if id(it) in drop:
                continue
            if it["y"] >= bottom - 0.5 and extra:
                it["y"] += extra
            out.append(it)
        items = out
        page["h"] = max(int(page["h"] + extra), 1)
    return items, page


def ghosts(doc, page, cap=40):
    """Copies of each repeating area's design for records 2, 3, 4... (the first record is the design
    itself). Only for drawing in the editor, so the other records can be seen while designing."""
    out = []
    for rep in [i for i in page["items"] if i.get("kind") == "repeater"]:
        db = find(doc, rep.get("db"))
        if not db:
            continue
        rows = sorted_rows(db, rep.get("sort", ""), rep.get("desc"), rep.get("limit", 0))[:cap]
        tmpl = [i for i in page["items"] if i.get("rep") == rep["id"]]
        w, h, gap = rep["w"], rep["h"], rep.get("gap", 16)
        cols = max(int(rep.get("cols", 1)), 1)
        for n, row in enumerate(rows):
            if n == 0:
                continue
            dx, dy = (n % cols) * (w + gap), (n // cols) * (h + gap)
            for t in tmpl:
                c = copy.deepcopy(t)
                c["id"] = "ghost_%s_%d" % (t["id"], n)
                c["x"] += dx
                c["y"] += dy
                for k in ("rep", "attach", "group", "link", "popup"):
                    c.pop(k, None)
                merge_item(doc, c, row)
                if not c.pop("hidden_empty", False):
                    out.append(c)
    return out


# -- CSV and photo folders --------------------------------------------------------------------------
def to_csv(db):
    out = io.StringIO()
    wr = csv.writer(out)
    wr.writerow(db["fields"])
    for r in db["rows"]:
        wr.writerow([r.get(f, "") for f in db["fields"]])
    return out.getvalue()


def from_csv(text):
    """(fields, rows) from CSV text; the first line names the fields."""
    lines = list(csv.reader(io.StringIO(text)))
    lines = [ln for ln in lines if any(c.strip() for c in ln)]
    if not lines:
        return [], []
    fields, seen = [], set()
    for f in lines[0]:
        f = clean_field(f)
        base, k = f, 2
        while f in seen:
            f, k = "%s_%d" % (base, k), k + 1
        seen.add(f)
        fields.append(f)
    rows = [{f: (ln[i].strip() if i < len(ln) else "") for i, f in enumerate(fields)} for ln in lines[1:]]
    return fields, rows


def photo_database(doc, folder, name="Photos"):
    db = new_database(name, ["photo", "name", "caption"])
    for fn in sorted(os.listdir(folder), key=str.lower):
        if fn.lower().endswith(PICTURES):
            aid = doc.add_asset(os.path.join(folder, fn))
            stem = os.path.splitext(fn)[0].replace("_", " ").replace("-", " ").strip()
            db["rows"].append(dict(photo=aid, name=stem, caption=stem))
    return db
