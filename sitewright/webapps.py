"""Objects that need a little server program on your own web host (PHP): polls, a blog with comments
and likes, and a shop. Each one lives in its own module and registers its object kinds here, so the
rest of the program only has to ask this file what exists."""
import html

REGISTRY = {}          # kind -> module describing it
MODULES = []


def register(module):
    MODULES.append(module)
    for kind in module.KINDS:
        REGISTRY[kind] = module


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def install(defaults, names):
    """Called once by model.py so the new kinds get their defaults and names."""
    from . import blog, polls, shop
    for m in (polls, blog, shop):
        register(m)
        for kind, spec in m.KINDS.items():
            defaults[kind] = dict(spec["defaults"])
            names[kind] = spec["name"]


def schemas():
    out = {}
    for m in MODULES:
        for kind, spec in m.KINDS.items():
            if spec.get("schema"):
                out[kind] = spec["schema"]
    return out


def all_items(doc):
    for lst in [p["items"] for p in doc.pages if p.get("type", "page") == "page"] + doc.all_master_lists():
        for it in lst:
            yield it


def files(doc):
    """{file name: text} of every helper file the site needs, from every module."""
    kinds = {it["kind"] for it in all_items(doc)}
    out = {}
    for m in MODULES:
        out.update(m.php_files(doc, kinds))
    return out


def paint(p, r, d, win):
    REGISTRY[d["kind"]].KINDS[d["kind"]]["paint"](p, r, d, win)


def export(d, css, files_, anames, tag, attr):
    from . import extras
    return REGISTRY[d["kind"]].KINDS[d["kind"]]["export"](d, css, files_, anames, extras.CONTEXT.get("doc"), tag, attr)


def insert(win, kind):
    """Put a new poll / blog / shop object on the page (below what is there) and open its settings."""
    from .model import new_item
    page = win.cur_page()
    below = max([d["y"] + d["h"] for d in page["items"]] or [20]) + 20
    d = new_item(kind, 40, round(min(below, max(int(page["h"]) - 200, 20))))
    win.target_list().append(d)
    spec = REGISTRY[kind].KINDS[kind]
    if spec.get("on_insert"):
        spec["on_insert"](win, d)
    win.reload({d["id"]})
    bottom = d["y"] + d["h"]
    if not win.master_mode and bottom + 40 > page["h"]:
        page["h"] = int(bottom + 40)
        win.reload({d["id"]})
    win.commit_if_changed("Add " + spec["name"].lower())
    win.show_properties()
