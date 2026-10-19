"""Starter page layouts (original designs) for Insert > Page from template."""
from .model import new_item


def _t(x, y, w, h, text, size=18, bold=False, color="#222222", align="left"):
    """Big bold text becomes a real heading, which search engines look for."""
    tag = ""
    if bold:
        tag = "h1" if size >= 40 else "h2" if size >= 28 else "h3" if size >= 22 else ""
    return new_item("text", x, y, w=w, h=h, text=text, size=size, bold=bold,
                    color=color, align=align, htag=tag)


def landing(W):
    items = [
        new_item("rect", 0, 0, w=W, h=360, fill="#1f3a5f"),
        _t(60, 110, W - 120, 70, "A headline that says it all", 44, True, "#ffffff"),
        _t(60, 190, W - 120, 60, "One sentence that explains what you offer.", 20, False, "#dfe8f5"),
        new_item("button", 60, 270, w=180, h=50, text="Get started"),
    ]
    cw = (W - 120 - 60) // 3
    for i, (h, b) in enumerate([("Fast", "Describe the first benefit here."),
                                ("Simple", "Describe the second benefit here."),
                                ("Yours", "Describe the third benefit here.")]):
        x = 60 + i * (cw + 30)
        items.append(new_item("rect", x, 420, w=cw, h=4, fill="#2b7de9"))
        items.append(_t(x, 440, cw, 36, h, 24, True))
        items.append(_t(x, 482, cw, 110, b, 17))
    return items, 680


def about(W):
    return [
        _t(60, 50, W - 120, 56, "About us", 40, True),
        new_item("image", 60, 130, w=340, h=300, fit="cover"),
        _t(430, 130, W - 490, 300, "Tell your story here. Who you are, what you do, "
           "and why people should care.", 19),
        new_item("line", 60, 470, w=W - 120, h=0, stroke="#cccccc", sw=1),
    ], 560


def contact(W):
    """A working contact page: details on the left, a form that really sends on the
    right, a map underneath. Edit or rebuild the form with Insert > Form designer."""
    from .forms import FORM_TEMPLATES, build_form
    items = [_t(60, 50, W - 120, 56, "Contact us", 40, True),
             _t(60, 130, 300, 150, "%companyname%\n%companyaddress1%\n%companyaddress3%\n"
                "%companyphone%\n%companyemail%", 18)]
    col = max(340, (W - 120) // 2)
    form, fy = build_form(FORM_TEMPLATES["Contact"], "Plain", x=W - 60 - col, y=130,
                          w=col, submit="Send message")
    items += form
    items.append(new_item("map", 60, fy + 20, w=W - 120, h=260, address="Your town, State"))
    return items, fy + 320


def gallery(W):
    items = [_t(60, 50, W - 120, 56, "Gallery", 40, True)]
    cw = (W - 120 - 40) // 3
    for r in range(2):
        for c in range(3):
            items.append(new_item("image", 60 + c * (cw + 20), 140 + r * 230,
                                  w=cw, h=210, fit="cover"))
    return items, 640


TEMPLATES = {"Landing page": landing, "About": about, "Contact": contact,
             "Gallery": gallery}


def build(name, width):
    out = TEMPLATES[name](width)
    return out if isinstance(out, tuple) else (out, 600)


# ---- Quick Build blocks: small ready-made groups inserted on the current page
def _heading_text(W):
    return [_t(0, 0, W - 80, 50, "A section heading", 32, True),
            _t(0, 60, W - 80, 90, "Write a few lines here that tell visitors what this "
               "section is about.", 18)], 160


def _call_to_action(W):
    return [new_item("rect", 0, 0, w=W - 80, h=140, fill="#1f3a5f", radius=10),
            _t(30, 24, W - 140, 44, "Ready to get started?", 28, True, "#ffffff"),
            new_item("button", 30, 80, w=180, h=44, text="Contact us")], 150


def _three_columns(W):
    cw = (W - 80 - 40) // 3
    items = []
    for i, (h, b) in enumerate([("One", "First point goes here."),
                                ("Two", "Second point goes here."),
                                ("Three", "Third point goes here.")]):
        x = i * (cw + 20)
        items.append(_t(x, 0, cw, 34, h, 22, True))
        items.append(_t(x, 40, cw, 90, b, 17))
    return items, 140


def _contact_block(W):
    return [_t(0, 0, 300, 34, "Contact us", 24, True),
            _t(0, 44, 300, 110, "%companyname%\n%companyaddress1%\n%companyphone%\n"
               "%companyemail%", 17)], 160


def _photo_text(W):
    return [new_item("image", 0, 0, w=300, h=200, fit="cover"),
            _t(330, 0, W - 410, 200, "Describe the picture or tell the story behind "
               "it here.", 18)], 210


def _social_strip(W):
    return [_t(0, 0, 160, 36, "Follow us", 18, True),
            new_item("social", 150, -2, w=220, h=40)], 44


BLOCKS = {"Heading and text": _heading_text, "Call to action": _call_to_action,
          "Three columns": _three_columns, "Contact details": _contact_block,
          "Photo and text": _photo_text, "Social strip": _social_strip}


def block(name, width):
    return BLOCKS[name](width)


# ---- whole-site templates for the Startup Assistant (original designs)
def _page(name, items, h):
    return dict(name=name, items=items, h=h)


def _shift(items, dy):
    for i in items:
        i["y"] += dy
    return items


def _site_business(W):
    home, hh = landing(W)
    about, ah = about_(W)
    contact_items, ch = contact(W)
    return [_page("Home", _shift(home, 60), hh + 60),
            _page("About", _shift(about, 60), ah + 60),
            _page("Contact", _shift(contact_items, 60), ch + 60)]


def about_(W):
    return about(W)


def _site_portfolio(W):
    head = [_t(60, 90, W - 120, 56, "My work", 40, True),
            _t(60, 150, W - 120, 40, "A selection of recent projects.", 20)]
    gal, gh = gallery(W)
    home = head + _shift(gal[1:], 110)
    ab, ah = about(W)
    ct, ch = contact(W)
    return [_page("Work", home, gh + 170), _page("About", _shift(ab, 60), ah + 60),
            _page("Contact", _shift(ct, 60), ch + 60)]


def _site_restaurant(W):
    hero = [new_item("rect", 0, 60, w=W, h=300, fill="#5b2a1f"),
            _t(60, 140, W - 120, 70, "Fresh food, made with care", 42, True, "#ffffff"),
            _t(60, 220, W - 120, 50, "Open every day from 11am to 9pm.", 20, False, "#f5ddd2"),
            new_item("button", 60, 290, w=200, h=50, text="See the menu")]
    menu = [_t(60, 90, W - 120, 56, "Menu", 40, True),
            new_item("table", 60, 170, w=W - 120, h=200, rows=5, cols=2,
                     cells=[["Dish", "Price"], ["House special", "$12"],
                            ["Soup of the day", "$6"], ["Garden salad", "$8"],
                            ["Dessert", "$5"]])]
    ct, ch = contact(W)
    return [_page("Home", hero, 420), _page("Menu", menu, 420),
            _page("Contact", _shift(ct, 60), ch + 60)]


def _site_church(W):
    hero = [_t(60, 110, W - 120, 70, "You are welcome here", 44, True),
            _t(60, 200, W - 120, 80, "Join us each week. Everyone is welcome.", 22),
            new_item("button", 60, 300, w=200, h=50, text="Service times")]
    times = [_t(60, 90, W - 120, 56, "Service times", 40, True),
             new_item("table", 60, 170, w=W - 120, h=170, rows=4, cols=2,
                      cells=[["Service", "Time"], ["Sunday morning", "10:00 am"],
                             ["Sunday evening", "6:00 pm"], ["Wednesday", "7:00 pm"]])]
    ct, ch = contact(W)
    return [_page("Home", hero, 420), _page("Services", times, 420),
            _page("Contact", _shift(ct, 60), ch + 60)]


def _site_event(W):
    hero = [new_item("rect", 0, 60, w=W, h=280, fill="#1f3a5f"),
            _t(60, 130, W - 120, 70, "Annual Community Day", 44, True, "#ffffff"),
            _t(60, 215, W - 120, 50, "Saturday, 10am to 4pm - free entry", 22, False, "#dfe8f5")]
    sched = [_t(60, 90, W - 120, 56, "Schedule", 40, True),
             new_item("table", 60, 170, w=W - 120, h=200, rows=5, cols=2,
                      cells=[["Time", "What's on"], ["10:00", "Opening"],
                             ["12:00", "Lunch"], ["2:00", "Games"], ["4:00", "Close"]])]
    ct, ch = contact(W)
    return [_page("Home", hero, 420), _page("Schedule", sched, 460),
            _page("Contact", _shift(ct, 60), ch + 60)]


def _site_blog(W):
    home = [_t(60, 90, W - 120, 56, "Latest news", 40, True)]
    cw = (W - 120 - 40) // 3
    for i in range(3):
        x = 60 + i * (cw + 20)
        home += [new_item("image", x, 170, w=cw, h=150, fit="cover"),
                 _t(x, 330, cw, 34, "Article title", 22, True),
                 _t(x, 370, cw, 70, "A short summary of the article goes here.", 16)]
    ab, ah = about(W)
    return [_page("News", home, 520), _page("About", _shift(ab, 60), ah + 60)]


SITE_TEMPLATES = {
    "Small business": _site_business, "Portfolio": _site_portfolio,
    "Restaurant": _site_restaurant, "Church or group": _site_church,
    "Event": _site_event, "Blog or news": _site_blog,
}


def build_site(name, width):
    return SITE_TEMPLATES[name](width)
