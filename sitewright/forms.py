"""Form builder: turns a list of fields and a look into page objects."""
import re

from .model import new_item

FORM_TEMPLATES = {
    "Contact": [
        dict(label="Your name", type="text", required=True),
        dict(label="Email address", type="email", required=True, name="email"),
        dict(label="Phone", type="text"),
        dict(label="Message", type="textarea", required=True),
    ],
    "Feedback": [
        dict(label="Your name", type="text"),
        dict(label="Email address", type="email", name="email"),
        dict(label="How did we do?", type="select",
             options="Excellent\nGood\nOkay\nPoor"),
        dict(label="Comments", type="textarea", required=True),
    ],
    "Booking or enquiry": [
        dict(label="Your name", type="text", required=True),
        dict(label="Email address", type="email", required=True, name="email"),
        dict(label="Phone", type="text"),
        dict(label="Date wanted", type="date"),
        dict(label="Number of people", type="select",
             options="1\n2\n3\n4\n5\n6\n7\n8 or more"),
        dict(label="Notes", type="textarea"),
    ],
    "Newsletter sign-up": [
        dict(label="Email address", type="email", required=True, name="email"),
        dict(label="I agree to receive emails", type="checkbox", required=True),
    ],
}

THEMES = {
    "Plain": dict(fill="#ffffff", stroke="#9aa3ad", sw=1, radius=4, color="#222222"),
    "Rounded": dict(fill="#ffffff", stroke="#9aa3ad", sw=1, radius=18, color="#222222"),
    "Soft": dict(fill="#eef2f7", stroke="", sw=0, radius=6, color="#222222"),
    "Boxed": dict(fill="#ffffff", stroke="#1f3a5f", sw=2, radius=0, color="#1f3a5f"),
    "Dark": dict(fill="#2b2f36", stroke="#555b66", sw=1, radius=4, color="#ffffff"),
    "Warm": dict(fill="#fff6ec", stroke="#e8832a", sw=1, radius=6, color="#5b3a14"),
}

SEND_COLOURS = dict(fill="#2b7de9", color="#ffffff")


def field_name(label, used):
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "field"
    name, n = base, 2
    while name in used:
        name, n = "%s_%d" % (base, n), n + 1
    used.add(name)
    return name


def build_form(fields, theme="Plain", x=60, y=60, w=420, title="", submit="Send",
               label_color="#222222"):
    """Return (items, bottom_y). Labels sit above the boxes; every box is a real
    form field, so the finished page sends the message."""
    look = THEMES.get(theme, THEMES["Plain"])
    items, used = [], set()
    cy = y
    if title:
        items.append(new_item("text", x, cy, w=w, h=40, text=title, size=26, bold=True,
                              color=label_color))
        cy += 52
    for f in fields:
        t = f.get("type", "text")
        name = f.get("name") or field_name(f.get("label", "field"), used)
        used.add(name)
        label = f.get("label", "")
        star = " *" if f.get("required") else ""
        if t in ("checkbox", "radio"):
            items.append(new_item("field", x, cy, w=w, h=30, ftype=t, name=name,
                                  label=label, required=bool(f.get("required")),
                                  fill="", stroke="", sw=0, color=look["color"]
                                  if theme != "Dark" else label_color))
            cy += 44
            continue
        items.append(new_item("text", x, cy, w=w, h=22, text=label + star, size=14,
                              bold=True, color=label_color))
        cy += 24
        h = 110 if t == "textarea" else 38
        extra = {}
        if t == "select":
            extra["options"] = f.get("options", "")
        items.append(new_item("field", x, cy, w=w, h=h, ftype=t, name=name, label="",
                              required=bool(f.get("required")), size=15, **look, **extra))
        cy += h + 16
    items.append(new_item("field", x, cy + 4, w=min(w, 180), h=46, ftype="submit", name="send",
                          label=submit, size=16, radius=look["radius"] if look["radius"] < 24 else 8,
                          **SEND_COLOURS, stroke="", sw=0))
    return items, cy + 60
