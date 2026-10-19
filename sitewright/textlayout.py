"""How the words of a text box are laid out: wrapped at the box width (a word that is wider
than the box is broken too), and for a text box the height follows the text."""
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QPalette, QTextCursor, QTextDocument,
                         QTextListFormat, QTextOption)

MIN_H = 24
FIT_KEYS = ("text", "size", "font", "bold", "italic", "align", "w", "listtype")
OVERFLOWS = [("hidden", "Hidden (cut off)"), ("visible", "Overflow (spills out)"),
             ("auto", "Auto scroll bar"), ("scroll", "Fixed scroll bar")]

# (value, name shown, Qt list style, CSS list-style-type, ul or ol)
LIST_STYLES = [
    ("", "No list", None, "", ""),
    ("bullet", "Bullets  \u2022", QTextListFormat.ListDisc, "disc", "ul"),
    ("circle", "Circles  \u25e6", QTextListFormat.ListCircle, "circle", "ul"),
    ("square", "Squares  \u25aa", QTextListFormat.ListSquare, "square", "ul"),
    ("number", "Numbers  1. 2. 3.", QTextListFormat.ListDecimal, "decimal", "ol"),
    ("alpha", "Letters  a. b. c.", QTextListFormat.ListLowerAlpha, "lower-alpha", "ol"),
    ("ualpha", "Capital letters  A. B. C.", QTextListFormat.ListUpperAlpha, "upper-alpha", "ol"),
    ("roman", "Roman  i. ii. iii.", QTextListFormat.ListLowerRoman, "lower-roman", "ol"),
    ("uroman", "Capital roman  I. II. III.", QTextListFormat.ListUpperRoman, "upper-roman", "ol"),
]
LIST_BY_VALUE = {v[0]: v for v in LIST_STYLES}
INDENT = 22


def document(d, width):
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(max(int(d.get("size", 18)), 1))
    f.setBold(bool(d.get("bold")))
    f.setItalic(bool(d.get("italic")))
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setDefaultFont(f)
    opt = QTextOption()
    opt.setAlignment({"center": Qt.AlignHCenter, "right": Qt.AlignRight,
                      "justify": Qt.AlignJustify}.get(d.get("align"), Qt.AlignLeft))
    opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    doc.setDefaultTextOption(opt)
    doc.setPlainText(d.get("text", ""))
    style = LIST_BY_VALUE.get(d.get("listtype", ""))
    if style and style[2] is not None and d.get("kind") == "text":
        doc.setIndentWidth(INDENT)
        fmt = QTextListFormat()
        fmt.setStyle(style[2])
        fmt.setIndent(1)
        if style[4] == "ol":
            fmt.setNumberSuffix(".")
        cur = QTextCursor(doc)
        cur.select(QTextCursor.Document)
        cur.createList(fmt)
    doc.setTextWidth(max(width, 1))
    return doc


def text_height(d, width=None):
    return document(d, d["w"] if width is None else width).size().height()


def grows(d):
    """Text boxes follow their text; buttons and the rest keep the height you gave them."""
    return d.get("kind") == "text" and d.get("autoh", True)


def fit_height(d):
    """Make a text box exactly as tall as its text. Returns True if the height changed."""
    if not grows(d):
        return False
    h = max(int(math.ceil(text_height(d))), MIN_H)
    if h == d.get("h"):
        return False
    d["h"] = h
    return True


def paint(p, r, d):
    """Draw the words inside r, clipped to it; buttons are centred up and down."""
    doc = document(d, r.width())
    top = 0.0
    if d.get("kind") == "button":
        top = max((r.height() - doc.size().height()) / 2, 0)
    ctx = QAbstractTextDocumentLayout.PaintContext()
    ctx.palette.setColor(QPalette.Text, QColor(d.get("color", "#222222")))
    mode = d.get("overflow", "hidden") if d.get("kind") == "text" else "hidden"
    p.save()
    if mode != "visible":
        p.setClipRect(r)
    p.translate(QPointF(r.left(), r.top() + top))
    doc.documentLayout().draw(p, ctx)
    p.restore()
    full = doc.size().height()
    if mode == "scroll" or (mode == "auto" and full > r.height() + 0.5):
        track = QRectF(r.right() - 11, r.top(), 11, r.height())      # a scroll bar on the right
        p.save()
        p.fillRect(track, QColor(235, 238, 242))
        thumb_h = r.height() * min(1.0, r.height() / max(full, 1))
        p.fillRect(QRectF(track.left() + 2, track.top() + 2, 7, max(thumb_h - 4, 12)), QColor(160, 168, 178))
        p.restore()
