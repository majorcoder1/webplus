"""Table tools: merge, sizes, autofit, delete, sort, formatting, AutoFormat, calendar, export. Must print ALL GOOD."""
import copy
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import QApplication

from sitewright import tablecore as tc
from sitewright.model import DEFAULTS

app = QApplication([])


def table(rows=4, cols=3, header=True):
    d = dict(DEFAULTS["table"], kind="table", id="t1", x=0, y=0)
    d = copy.deepcopy(d)
    d["rows"], d["cols"], d["header"] = rows, cols, header
    d["cells"] = [["r%dc%d" % (i, j) for j in range(cols)] for i in range(rows)]
    return d


# selecting
d = table()
tc.select_rows(d, 1, 2)
assert d["sel"] == [1, 0, 2, 2]
tc.select_cols(d, 2, 0)
assert d["sel"] == [0, 0, 3, 2]
d["sel"] = [9, 9, 0, 0]
assert tc.clamp_sel(d) == [0, 0, 3, 2]

# merge and separate
d = table()
assert tc.merge_cells(d, 1, 0, 2, 1)
assert d["merges"] == [[1, 0, 2, 2]]
assert d["cells"][1][0] == "r1c0 r1c1 r2c0 r2c1" and d["cells"][2][1] == ""
spans, covered = tc.layout(d)
assert spans == {(1, 0): (2, 2)} and covered == {(1, 1), (2, 0), (2, 1)}
assert not tc.merge_cells(d, 0, 0, 0, 0), "one cell cannot merge"
assert tc.merge_cells(d, 0, 0, 1, 1)           # overlaps the old block: the old one goes
assert d["merges"] == [[0, 0, 2, 2]]
assert tc.separate_cells(d, 0, 0, 3, 2) == 1 and d["merges"] == []

# sizes
d = table()
assert abs(sum(tc.fractions(d, "colw", 3)) - 1) < 1e-9
tc.set_col_width(d, 0, 0, 240)
cw = tc.fractions(d, "colw", 3)
assert abs(cw[0] * d["w"] - 240) < 1 and abs(sum(cw) - 1) < 1e-9 and abs(cw[1] - cw[2]) < 1e-9
tc.set_row_height(d, 1, 2, 20)
rh = tc.fractions(d, "rowh", 4)
assert abs(rh[1] * d["h"] - 20) < 1 and abs(sum(rh) - 1) < 1e-9
tc.distribute_cols(d)
tc.distribute_rows(d)
assert d["colw"] == [] and d["rowh"] == []
e = tc.edges(d, 300, 3, "colw")
assert e == [0.0, 100.0, 200.0, 300.0]

# autofit
d = table()
d["cells"][2][1] = "a much longer piece of text"
fm = QFontMetrics(QFont("Sans Serif", 12))
tc.autofit_cols(d, fm)
cw = tc.fractions(d, "colw", 3)
assert cw[1] > cw[0] and cw[1] > cw[2]
assert abs(sum(cw) * d["w"] - d["w"]) < 1e-6 and d["w"] > 100
d["cells"][1][0] = "two\nlines"
tc.autofit_rows(d, fm)
rh = tc.fractions(d, "rowh", 4)
assert rh[1] > rh[0]

# delete rows / columns keep merges and formats in step
d = table(5, 4)
tc.merge_cells(d, 3, 0, 4, 1)
tc.set_fmt(d, 4, 3, 4, 3, fill="#ff0000")
assert tc.delete_rows(d, 1, 2)
assert d["rows"] == 3 and d["merges"] == [[1, 0, 2, 2]]
assert tc.cell_fmt(d, 2, 3)["fill"] == "#ff0000"
assert tc.delete_cols(d, 3, 3) and d["cols"] == 3 and "2,3" not in d["fmt"]
assert not tc.delete_rows(d, 0, 2), "the last row cannot be deleted"
assert tc.delete_cols(d, 1, 1) and d["merges"] == [[1, 0, 2, 1]] or d["merges"] == []

# sorting: header stays, numbers sort as numbers, formats travel with their row
d = table(4, 2)
d["cells"] = [["Name", "Qty"], ["pear", "10"], ["apple", "9"], ["fig", "100"]]
tc.set_fmt(d, 3, 0, 3, 1, bold=True)
assert tc.sort_rows(d, 1, True)
assert [r[0] for r in d["cells"]] == ["Name", "apple", "pear", "fig"]
assert tc.cell_fmt(d, 3, 0).get("bold") is True and tc.cell_fmt(d, 1, 0) == {}
assert tc.sort_rows(d, 0, False)
assert [r[0] for r in d["cells"]] == ["Name", "pear", "fig", "apple"]
d["merges"] = [[1, 0, 1, 2]]
assert not tc.sort_rows(d, 0), "no sorting through merged cells"

# formatting
d = table()
tc.set_fmt(d, 0, 0, 1, 1, fill="#00ff00", align="center", nonsense=1)
assert len(d["fmt"]) == 4 and d["fmt"]["1,1"] == {"fill": "#00ff00", "align": "center"}
tc.set_fmt(d, 0, 0, 1, 1, fill=None, align="")
assert d["fmt"] == {}

# AutoFormat
d = table()
for name in tc.AUTOFORMATS:
    tc.apply_autoformat(d, name)
    assert d["hfill"] and "band" in d
tc.apply_autoformat(d, "Dark")
assert d["color"] == "#e2e8f0"
tc.apply_autoformat(d, "Blue header")
assert d["color"] == "#222222" and d["hfill"] == "#1f3a5f"

# calendar: October 2026 starts on a Thursday, 31 days
d = table()
tc.make_calendar(d, 2026, 10)
assert d["rows"] == 8 and d["cols"] == 7
assert d["cells"][0][0] == "October 2026" and d["merges"] == [[0, 0, 1, 7]]
assert d["cells"][1] == ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
days = [x for row in d["cells"][2:] for x in row if x]
assert days == [str(i) for i in range(1, 32)]
assert d["cells"][2][4] == "1"
tc.make_calendar(d, 2026, 10, monday_first=True)
assert d["cells"][1][0] == "Mon" and d["cells"][2][3] == "1"

# resize keeps things consistent
d = table(4, 4)
tc.merge_cells(d, 2, 2, 3, 3)
tc.resize(d, 3, 3)
assert d["merges"] == [[2, 2, 1, 1]] and len(d["cells"]) == 3 and len(d["cells"][0]) == 3

# drawing and export honour all of it
from sitewright import extras
d = table(4, 3)
tc.merge_cells(d, 1, 0, 1, 2)
tc.set_fmt(d, 2, 0, 2, 0, fill="#ffee00", bold=True, align="right")
d["band"] = "#eeeeee"
tc.set_col_width(d, 0, 0, 100)
html_ = extras.export_extra(d, ["left:0px", "top:0px", "width:%dpx" % d["w"], "height:%dpx" % d["h"]],
                            "table", "", {}, {})
assert 'colspan="3"' in html_ and "<colgroup>" in html_ and "#ffee00" in html_
assert "font-weight:bold" in html_ and "text-align:right" in html_ and "#eeeeee" in html_
assert html_.count("<tr") == 4
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtCore import QRectF


class W:
    table_marks = d
img = QImage(500, 200, QImage.Format_ARGB32)
img.fill(0xffffffff)
pp = QPainter(img)
extras.paint_table(pp, QRectF(10, 10, 480, 150), d, W())
pp.end()
print("ALL GOOD")
