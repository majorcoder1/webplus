"""Makes the links in a PDF written by Qt clickable. Qt leaves an empty annotation list on every page;
this adds one link box per link, as an appended update, so nothing already in the file is touched."""
import re
from urllib.parse import quote


def _pdf_string(s):
    s = quote(s, safe="/:?&=#%+@~!$*,;-._")           # plain ASCII only
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def add_links(path, pages):
    """pages: one list per PDF page of (x0, y0, x1, y1, kind, value) with the box in PDF points measured
    from the top-left of the page. kind 'uri' (value = address) or 'page' (value = PDF page number from 0)."""
    with open(path, "rb") as f:
        data = f.read()
    if not any(pages):
        return 0
    prev = int(re.findall(rb"startxref\s+(\d+)", data)[-1])
    trailer = data[data.rfind(b"trailer"):]
    size = int(re.search(rb"/Size\s+(\d+)", trailer).group(1))
    root = re.search(rb"/Root\s+(\d+)\s+0\s+R", trailer).group(1).decode()
    info = re.search(rb"/Info\s+(\d+)\s+0\s+R", trailer)
    kids = [int(n) for n in re.findall(rb"(\d+)\s+0\s+R", re.search(rb"/Kids\s*\[([^\]]*)\]", data).group(1))]
    if len(kids) != len(pages):
        return 0
    page_h = {}
    for k in kids:
        body = re.search(rb"\n%d 0 obj\n(.*?)endobj" % k, data, re.S).group(1)
        mb = re.search(rb"/MediaBox\s*\[\s*[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s*\]", body)
        page_h[k] = float(mb.group(1))
    out = bytearray(data)
    if not out.endswith(b"\n"):
        out += b"\n"
    entries = []                       # (object number, offset)
    next_obj = size
    count = 0

    def put(num, body):
        entries.append((num, len(out)))
        out.extend(b"%d 0 obj\n%s\nendobj\n" % (num, body))

    for k, links in zip(kids, pages):
        if not links:
            continue
        body = re.search(rb"\n%d 0 obj\n(.*?)endobj" % k, data, re.S).group(1)
        annots = re.search(rb"/Annots\s+(\d+)\s+0\s+R", body)
        if annots is None:
            continue                   # not a page Qt gave a list to; leave it alone
        refs = []
        for x0, y0, x1, y1, kind, value in links:
            h = page_h[k]
            rect = "[%.2f %.2f %.2f %.2f]" % (x0, h - y1, x1, h - y0)
            if kind == "uri":
                act = "/A << /S /URI /URI %s >>" % _pdf_string(value)
            elif kind == "page" and 0 <= value < len(kids):
                act = "/Dest [%d 0 R /XYZ 0 %.2f null]" % (kids[value], page_h[kids[value]])
            else:
                continue
            put(next_obj, ("<< /Type /Annot /Subtype /Link /Rect %s /Border [0 0 0] %s >>" % (rect, act)).encode())
            refs.append(next_obj)
            next_obj += 1
            count += 1
        put(int(annots.group(1)), ("[ " + " ".join("%d 0 R" % r for r in refs) + " ]").encode())
    xref_at = len(out)
    out += b"xref\n"
    for num, off in sorted(entries):
        out += b"%d 1\n%010d 00000 n \n" % (num, off)
    out += (b"trailer\n<< /Size %d /Root %s 0 R %s/Prev %d >>\nstartxref\n%d\n%%%%EOF\n" % (
        next_obj, root.encode(), (b"/Info %s 0 R " % info.group(1)) if info else b"", prev, xref_at))
    with open(path, "wb") as f:
        f.write(out)
    return count
