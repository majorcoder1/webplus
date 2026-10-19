"""Table logic, kept apart from the screen so it can be tested: cell ranges, merged cells,
row and column sizes, sorting, per-cell formatting, AutoFormat presets and calendars.

A table object holds: rows, cols, cells (rows x cols of text), plus optional
  colw / rowh  - share of the width / height for each column / row (lists of fractions)
  merges       - [[row, col, rowspan, colspan], ...]
  fmt          - {"row,col": {fill, color, align, bold, italic, valign}}
  band         - colour for every other body row
  sel          - [row1, col1, row2, col2] the cells the table tools work on
"""
import calendar

FMT_KEYS = ("fill", "color", "align", "bold", "italic", "valign")


def _cells(d):
    return d.setdefault("cells", [[""]])


def clamp_sel(d):
    r, c = max(d["rows"], 1), max(d["cols"], 1)
    s = list(d.get("sel") or [0, 0, 0, 0])
    s = (s + [0, 0, 0, 0])[:4]
    r1, r2 = sorted((min(max(s[0], 0), r - 1), min(max(s[2], 0), r - 1)))
    c1, c2 = sorted((min(max(s[1], 0), c - 1), min(max(s[3], 0), c - 1)))
    d["sel"] = [r1, c1, r2, c2]
    return d["sel"]


def fractions(d, key, n):
    """The size share of each row/column; equal when none are set or the count is out of date."""
    fr = d.get(key) or []
    if len(fr) != n or any(f <= 0 for f in fr):
        return [1.0 / n] * n
    t = float(sum(fr))
    return [f / t for f in fr]


def edges(d, total, n, key):
    """Cumulative positions: n+1 numbers from 0 to total."""
    out, acc = [0.0], 0.0
    for f in fractions(d, key, n):
        acc += f * total
        out.append(acc)
    out[-1] = float(total)
    return out


def layout(d):
    """(origin spans, covered): {(r,c): (rowspan, colspan)} and the set of hidden cells."""
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    spans, covered = {}, set()
    for r, c, rs, cs in d.get("merges") or []:
        if r >= rows or c >= cols:
            continue
        rs, cs = min(rs, rows - r), min(cs, cols - c)
        if rs * cs <= 1:
            continue
        spans[(r, c)] = (rs, cs)
        for i in range(r, r + rs):
            for j in range(c, c + cs):
                if (i, j) != (r, c):
                    covered.add((i, j))
    return spans, covered


def cell_fmt(d, r, c):
    return (d.get("fmt") or {}).get("%d,%d" % (r, c)) or {}


def text_at(d, r, c):
    try:
        return d["cells"][r][c]
    except (IndexError, KeyError):
        return ""


# -- selecting -------------------------------------------------------------
def select_rows(d, r1=None, r2=None):
    s = clamp_sel(d)
    r1 = s[0] if r1 is None else r1
    r2 = s[2] if r2 is None else r2
    d["sel"] = [min(r1, r2), 0, max(r1, r2), max(d["cols"], 1) - 1]
    return clamp_sel(d)


def select_cols(d, c1=None, c2=None):
    s = clamp_sel(d)
    c1 = s[1] if c1 is None else c1
    c2 = s[3] if c2 is None else c2
    d["sel"] = [0, min(c1, c2), max(d["rows"], 1) - 1, max(c1, c2)]
    return clamp_sel(d)


def select_all(d):
    d["sel"] = [0, 0, max(d["rows"], 1) - 1, max(d["cols"], 1) - 1]
    return clamp_sel(d)


# -- merging ---------------------------------------------------------------
def merge_cells(d, r1, c1, r2, c2):
    """Join the cells in the range into one. The words of all of them go into the first."""
    r1, r2 = sorted((r1, r2))
    c1, c2 = sorted((c1, c2))
    if (r2 - r1 + 1) * (c2 - c1 + 1) < 2:
        return False
    keep = []
    for m in d.get("merges") or []:
        r, c, rs, cs = m
        if r + rs - 1 < r1 or r > r2 or c + cs - 1 < c1 or c > c2:
            keep.append(m)           # does not touch the new block
    words = []
    for i in range(r1, r2 + 1):
        for j in range(c1, c2 + 1):
            t = text_at(d, i, j).strip()
            if t:
                words.append(t)
            if (i, j) != (r1, c1) and i < len(d["cells"]) and j < len(d["cells"][i]):
                d["cells"][i][j] = ""
    d["cells"][r1][c1] = " ".join(words)
    keep.append([r1, c1, r2 - r1 + 1, c2 - c1 + 1])
    d["merges"] = keep
    return True


def separate_cells(d, r1, c1, r2, c2):
    r1, r2 = sorted((r1, r2))
    c1, c2 = sorted((c1, c2))
    keep, n = [], 0
    for m in d.get("merges") or []:
        r, c, rs, cs = m
        if r + rs - 1 < r1 or r > r2 or c + cs - 1 < c1 or c > c2:
            keep.append(m)
        else:
            n += 1
    d["merges"] = keep
    return n


# -- sizes -----------------------------------------------------------------
def distribute_rows(d):
    d["rowh"] = []


def distribute_cols(d):
    d["colw"] = []


def set_col_width(d, c1, c2, px):
    """Make columns c1..c2 px wide; the others share what is left. The table keeps its width."""
    cols = max(d["cols"], 1)
    c1, c2 = sorted((c1, c2))
    total = float(d["w"])
    fr = fractions(d, "colw", cols)
    want = max(px, 8) / total
    n = c2 - c1 + 1
    want = min(want, (1 - 0.02 * (cols - n)) / n) if cols > n else 1.0 / n
    others = [i for i in range(cols) if not c1 <= i <= c2]
    rest = 1 - want * n
    old = sum(fr[i] for i in others) or 1.0
    for i in range(cols):
        fr[i] = want if c1 <= i <= c2 else fr[i] / old * rest
    d["colw"] = fr


def set_row_height(d, r1, r2, px):
    rows = max(d["rows"], 1)
    r1, r2 = sorted((r1, r2))
    total = float(d["h"])
    fr = fractions(d, "rowh", rows)
    want = max(px, 8) / total
    n = r2 - r1 + 1
    want = min(want, (1 - 0.02 * (rows - n)) / n) if rows > n else 1.0 / n
    others = [i for i in range(rows) if not r1 <= i <= r2]
    rest = 1 - want * n
    old = sum(fr[i] for i in others) or 1.0
    for i in range(rows):
        fr[i] = want if r1 <= i <= r2 else fr[i] / old * rest
    d["rowh"] = fr


def autofit_cols(d, metrics, c1=None, c2=None):
    """Each column in range as wide as its longest text (plus padding). The table width follows."""
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    c1 = 0 if c1 is None else c1
    c2 = cols - 1 if c2 is None else c2
    spans, covered = layout(d)
    cur = [f * d["w"] for f in fractions(d, "colw", cols)]
    for c in range(min(c1, c2), max(c1, c2) + 1):
        w = 30.0
        for r in range(rows):
            if (r, c) in covered or spans.get((r, c), (1, 1))[1] > 1:
                continue
            w = max(w, metrics.horizontalAdvance(text_at(d, r, c)) + 20)
        cur[c] = w
    total = sum(cur)
    d["w"] = int(round(total))
    d["colw"] = [w / total for w in cur]


def autofit_rows(d, metrics, r1=None, r2=None):
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    r1 = 0 if r1 is None else r1
    r2 = rows - 1 if r2 is None else r2
    cur = [f * d["h"] for f in fractions(d, "rowh", rows)]
    for r in range(min(r1, r2), max(r1, r2) + 1):
        lines = max([1] + [text_at(d, r, c).count("\n") + 1 for c in range(cols)])
        cur[r] = metrics.height() * lines + 14
    total = sum(cur)
    d["h"] = int(round(total))
    d["rowh"] = [h / total for h in cur]


# -- rows and columns ------------------------------------------------------
def delete_rows(d, r1, r2):
    rows = max(d["rows"], 1)
    r1, r2 = sorted((r1, r2))
    r1, r2 = max(r1, 0), min(r2, rows - 1)
    if r2 - r1 + 1 >= rows:
        return False                      # keep at least one row
    n = r2 - r1 + 1
    del d["cells"][r1:r2 + 1]
    merges = []
    for r, c, rs, cs in d.get("merges") or []:
        last = r + rs - 1
        if last < r1:
            merges.append([r, c, rs, cs])
        elif r > r2:
            merges.append([r - n, c, rs, cs])
        else:
            gone = min(last, r2) - max(r, r1) + 1
            rs2 = rs - gone
            if rs2 >= 1:
                merges.append([min(r, r1), c, rs2, cs])
    d["merges"] = merges
    fmt = {}
    for k, v in (d.get("fmt") or {}).items():
        i, j = map(int, k.split(","))
        if i < r1:
            fmt[k] = v
        elif i > r2:
            fmt["%d,%d" % (i - n, j)] = v
    d["fmt"] = fmt
    d["rows"] = rows - n
    d["rowh"] = []
    clamp_sel(d)
    return True


def delete_cols(d, c1, c2):
    cols = max(d["cols"], 1)
    c1, c2 = sorted((c1, c2))
    c1, c2 = max(c1, 0), min(c2, cols - 1)
    if c2 - c1 + 1 >= cols:
        return False
    n = c2 - c1 + 1
    for row in d["cells"]:
        del row[c1:c2 + 1]
    merges = []
    for r, c, rs, cs in d.get("merges") or []:
        last = c + cs - 1
        if last < c1:
            merges.append([r, c, rs, cs])
        elif c > c2:
            merges.append([r, c - n, rs, cs])
        else:
            gone = min(last, c2) - max(c, c1) + 1
            cs2 = cs - gone
            if cs2 >= 1:
                merges.append([r, min(c, c1), rs, cs2])
    d["merges"] = merges
    fmt = {}
    for k, v in (d.get("fmt") or {}).items():
        i, j = map(int, k.split(","))
        if j < c1:
            fmt[k] = v
        elif j > c2:
            fmt["%d,%d" % (i, j - n)] = v
    d["fmt"] = fmt
    d["cols"] = cols - n
    d["colw"] = []
    clamp_sel(d)
    return True


def resize(d, rows, cols):
    """Change the table size (rows/columns are added or dropped at the end)."""
    old_r, old_c = d["rows"], d["cols"]
    d["cells"] = [[text_at(d, i, j) for j in range(cols)] for i in range(rows)]
    d["rows"], d["cols"] = rows, cols
    if rows != old_r:
        d["rowh"] = []
    if cols != old_c:
        d["colw"] = []
    merges = []
    for r, c, rs, cs in d.get("merges") or []:
        if r < rows and c < cols:
            merges.append([r, c, min(rs, rows - r), min(cs, cols - c)])
    d["merges"] = merges
    d["fmt"] = {k: v for k, v in (d.get("fmt") or {}).items()
                if int(k.split(",")[0]) < rows and int(k.split(",")[1]) < cols}
    clamp_sel(d)


# -- sorting ---------------------------------------------------------------
def _key(text):
    t = text.strip().replace(",", "")
    try:
        return (0, float(t), "")
    except ValueError:
        return (1, 0.0, text.strip().lower())


def sort_rows(d, col, ascending=True):
    """Sort the body rows by one column (the header row stays on top). Not allowed with merged cells."""
    if d.get("merges"):
        return False
    start = 1 if d.get("header") else 0
    rows = max(d["rows"], 1)
    order = sorted(range(start, rows), key=lambda i: _key(text_at(d, i, col)), reverse=not ascending)
    body = [d["cells"][i] for i in order]
    d["cells"][start:] = body
    fmt = d.get("fmt") or {}
    new = {k: v for k, v in fmt.items() if int(k.split(",")[0]) < start}
    for new_i, old_i in zip(range(start, rows), order):
        for k, v in fmt.items():
            i, j = map(int, k.split(","))
            if i == old_i:
                new["%d,%d" % (new_i, j)] = v
    d["fmt"] = new
    return True


# -- formatting ------------------------------------------------------------
def set_fmt(d, r1, c1, r2, c2, **kw):
    """Give every cell in the range these looks. A value of None clears that one look."""
    r1, r2 = sorted((r1, r2))
    c1, c2 = sorted((c1, c2))
    fmt = d.setdefault("fmt", {})
    for i in range(r1, r2 + 1):
        for j in range(c1, c2 + 1):
            f = fmt.setdefault("%d,%d" % (i, j), {})
            for k, v in kw.items():
                if k not in FMT_KEYS:
                    continue
                if v is None or v == "":
                    f.pop(k, None)
                else:
                    f[k] = v
            if not f:
                fmt.pop("%d,%d" % (i, j), None)


def clear_fmt(d):
    d["fmt"] = {}


AUTOFORMATS = {
    "Plain": dict(header=True, hfill="#e8ecf1", hcolor="#222222", fill="#ffffff", band="",
                  stroke="#c8ced6", sw=1),
    "Blue header": dict(header=True, hfill="#1f3a5f", hcolor="#ffffff", fill="#ffffff", band="",
                        stroke="#c8ced6", sw=1),
    "Grey stripes": dict(header=True, hfill="#4b5868", hcolor="#ffffff", fill="#ffffff",
                         band="#eef1f5", stroke="#d5dae1", sw=1),
    "Green stripes": dict(header=True, hfill="#1f7a4d", hcolor="#ffffff", fill="#ffffff",
                          band="#e6f4ec", stroke="#c7e0d1", sw=1),
    "Warm": dict(header=True, hfill="#d9661a", hcolor="#ffffff", fill="#fff9f2", band="#fdeedd",
                 stroke="#f1d3b5", sw=1),
    "Dark": dict(header=True, hfill="#0f172a", hcolor="#e2e8f0", fill="#1e293b", band="#273449",
                 stroke="#334155", sw=1, color="#e2e8f0"),
    "Lines only": dict(header=True, hfill="#ffffff", hcolor="#111111", fill="#ffffff", band="",
                       stroke="#999999", sw=1),
    "No lines": dict(header=True, hfill="#f3f5f8", hcolor="#222222", fill="#ffffff", band="",
                     stroke="", sw=0),
}


def apply_autoformat(d, name):
    preset = AUTOFORMATS[name]
    for k, v in preset.items():
        d[k] = v
    if "color" not in preset and d.get("color") == "#e2e8f0":
        d["color"] = "#222222"           # leaving the Dark preset: put the text colour back
    clear_fmt(d)


# -- calendar --------------------------------------------------------------
def calendar_cells(year, month, monday_first=False):
    """(title, weekday names, weeks) - weeks is always 6 rows of 7 strings."""
    cal = calendar.Calendar(firstweekday=0 if monday_first else 6)
    weeks = [[("" if day == 0 else str(day)) for day in wk] for wk in cal.monthdayscalendar(year, month)]
    while len(weeks) < 6:
        weeks.append([""] * 7)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if not monday_first:
        names = names[-1:] + names[:-1]
    return "%s %d" % (calendar.month_name[month], year), names, weeks


def make_calendar(d, year, month, monday_first=False):
    """Turn d into a month calendar: title row (merged), weekday row, six week rows."""
    title, names, weeks = calendar_cells(year, month, monday_first)
    cells = [[title] + [""] * 6, names] + weeks
    d.update(rows=8, cols=7, cells=cells, header=True, merges=[[0, 0, 1, 7]], colw=[], rowh=[],
             fmt={}, sel=[0, 0, 0, 0])
    for j in range(7):
        set_fmt(d, 0, j, 0, j, align="center", bold=True)
        set_fmt(d, 1, j, 1, j, align="center", bold=True, fill="#eef1f5", color="#222222")
    for i in range(2, 8):
        for j in range(7):
            set_fmt(d, i, j, i, j, align="right", valign="top")
    return d


# -- insert rows/columns, fill ---------------------------------------------
def insert_rows(d, at, n=1):
    """Add n empty rows so the first new one is row number `at` (0 = above everything)."""
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    at = min(max(at, 0), rows)
    d["cells"] = d["cells"][:at] + [[""] * cols for _ in range(n)] + d["cells"][at:]
    merges = []
    for r, c, rs, cs in d.get("merges") or []:
        if r >= at:
            merges.append([r + n, c, rs, cs])
        elif r + rs > at:
            merges.append([r, c, rs + n, cs])      # the new rows fall inside a merged block
        else:
            merges.append([r, c, rs, cs])
    d["merges"] = merges
    fmt = {}
    for k, v in (d.get("fmt") or {}).items():
        i, j = map(int, k.split(","))
        fmt["%d,%d" % (i + n if i >= at else i, j)] = v
    d["fmt"] = fmt
    d["rows"] = rows + n
    d["rowh"] = []
    clamp_sel(d)


def insert_cols(d, at, n=1):
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    at = min(max(at, 0), cols)
    d["cells"] = [row[:at] + [""] * n + row[at:] for row in d["cells"]]
    merges = []
    for r, c, rs, cs in d.get("merges") or []:
        if c >= at:
            merges.append([r, c + n, rs, cs])
        elif c + cs > at:
            merges.append([r, c, rs, cs + n])
        else:
            merges.append([r, c, rs, cs])
    d["merges"] = merges
    fmt = {}
    for k, v in (d.get("fmt") or {}).items():
        i, j = map(int, k.split(","))
        fmt["%d,%d" % (i, j + n if j >= at else j)] = v
    d["fmt"] = fmt
    d["cols"] = cols + n
    d["colw"] = []
    clamp_sel(d)


def fill_down(d, r1, c1, r2, c2):
    """Copy the top cell of each chosen column down through the range."""
    for j in range(c1, c2 + 1):
        top = text_at(d, r1, j)
        for i in range(r1 + 1, r2 + 1):
            d["cells"][i][j] = top


def fill_right(d, r1, c1, r2, c2):
    for i in range(r1, r2 + 1):
        left = text_at(d, i, c1)
        for j in range(c1 + 1, c2 + 1):
            d["cells"][i][j] = left
