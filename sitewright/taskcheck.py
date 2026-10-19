"""Task Monitor: things worth fixing before the site is published."""


def check(doc):
    """Return [(message, page_id, item_id)] - page_id/item_id may be ''."""
    out = []
    ids = {p["id"] for p in doc.pages}
    has_field = False
    lists = [(p["name"], p["id"], p["items"]) for p in doc.pages
             if p.get("type", "page") == "page"]
    lists += [(name, "", items) for _m, name, items in doc.all_masters()]
    for name, pid, items in lists:
        if not items and pid:
            out.append(("Page '%s' is empty." % name, pid, ""))
        for it in items:
            kind = it["kind"]
            where = "'%s'" % name
            if kind == "image":
                if not it.get("asset"):
                    out.append(("Empty picture frame on %s." % where, pid, it["id"]))
                elif not it.get("alt"):
                    out.append(("Picture on %s has no alt text." % where, pid, it["id"]))
            if kind == "field":
                has_field = True
                if it.get("ftype") == "captcha" and not str(it.get("answer", "")).strip():
                    out.append(("The CAPTCHA question on %s has no answer set." % where, pid, it["id"]))
                if it.get("ftype") == "recaptcha" and not (it.get("rc_site") and it.get("rc_secret")):
                    out.append(("The reCAPTCHA on %s needs its site key and secret key "
                                "(from google.com/recaptcha)." % where, pid, it["id"]))
                if it.get("ftype") in ("captcha", "recaptcha") and getattr(doc, "form_mode", "php") != "php":
                    out.append(("A CAPTCHA only works when the form is sent by the PHP script "
                                "(Insert > Form email address).", pid, it["id"]))
            link = it.get("link", "")
            if link.startswith("page:") and link[5:] not in ids:
                out.append(("A link on %s points to a page that was deleted." % where,
                            pid, it["id"]))
            if kind == "rssreader" and not (it.get("url") or "").strip():
                out.append(("The RSS reader on %s has no feed address." % where, pid, it["id"]))
            if kind == "map" and not it.get("address"):
                out.append(("Map on %s has no address." % where, pid, it["id"]))
            if kind == "video" and not it.get("url"):
                out.append(("Video on %s has no address." % where, pid, it["id"]))
            if kind == "poll" and len([o for o in (it.get("options") or "").splitlines() if o.strip()]) < 2:
                out.append(("The poll on %s needs at least two choices." % where, pid, it["id"]))
            if kind == "blog" and not [p for p in doc.blog["posts"] if p.get("published", True)]:
                out.append(("The blog on %s has no published posts (Tools > Blog manager)." % where, pid, it["id"]))
            if kind == "product":
                prod = next((p for p in doc.shop["products"] if p["id"] == it.get("product")), None)
                if prod is None:
                    out.append(("A product card on %s has no product chosen (Tools > Shop manager)." % where, pid, it["id"]))
                elif not prod.get("active", True):
                    out.append(("The product '%s' on %s is hidden, so its card will not show." % (prod["name"], where), pid, it["id"]))
    kinds_all = {it["kind"] for _n, _p, items in lists for it in items}
    if kinds_all & {"product", "productgrid", "cart"}:
        s = doc.shop
        prov = s.get("provider")
        if not s["products"]:
            out.append(("The shop has no products yet (Tools > Shop manager).", "", ""))
        if prov == "paypal" and not (s.get("paypal_client", "").strip() or s.get("paypal_email", "").strip()):
            out.append(("PayPal is chosen but has no Client ID or email (Tools > Shop manager > Payments).", "", ""))
        if prov == "stripe" and not s.get("stripe_secret", "").strip():
            out.append(("Stripe is chosen but has no secret key (Tools > Shop manager > Payments).", "", ""))
        if prov == "shopify" and not s.get("shopify_domain", "").strip():
            out.append(("Shopify is chosen but has no store address (Tools > Shop manager > Payments).", "", ""))
        if prov == "woocommerce" and not s.get("woo_url", "").strip():
            out.append(("WooCommerce is chosen but has no store address (Tools > Shop manager > Payments).", "", ""))
        for p in s["products"]:
            if p.get("active", True) and float(p.get("price") or 0) <= 0:
                out.append(("The product '%s' has no price." % p["name"], "", ""))
            if prov == "shopify" and p.get("active", True) and not str(p.get("shopify_variant", "")).strip():
                out.append(("The product '%s' is not linked to Shopify (no variant number)." % p["name"], "", ""))
            if prov == "woocommerce" and p.get("active", True) and not str(p.get("woo_id", "")).strip():
                out.append(("The product '%s' is not linked to WooCommerce (no product number)." % p["name"], "", ""))
    if has_field and not doc.form_email and getattr(doc, "form_mode", "php") != "custom":
        out.append(("The form has no email address (Insert > Form email address).", "", ""))
    # members, search and sign-up
    if any(p.get("protect") for p in doc.pages) and not getattr(doc, "members", []):
        out.append(("A page is members-only but there are no members yet "
                    "(Tools > Members and protected pages).", "", ""))
    for p in doc.pages:
        if p.get("type", "page") != "page":
            continue
        kinds = {i["kind"] for i in p["items"]}
        for it in p["items"]:
            if it["kind"] == "search" and not it.get("link") and "searchresults" not in kinds:
                out.append(("The search box on '%s' has no results page: put a Search results "
                            "object on a page and link the box to it." % p["name"], p["id"], it["id"]))
            if it["kind"] == "login" and not getattr(doc, "members", []):
                out.append(("The login form on '%s' has no members to sign in." % p["name"],
                            p["id"], it["id"]))
    # search engine checks
    seo = getattr(doc, "seo", {}) or {}
    seen_desc, seen_title = {}, {}
    for p in doc.pages:
        if p.get("type", "page") != "page":
            continue
        desc = (p.get("description") or "").strip()
        eff = desc or (seo.get("description") or "").strip()
        title = (p.get("title") or p["name"]).strip()
        if not eff:
            out.append(("Page '%s' has no description for search engines "
                        "(Properties > Search engine optimisation)." % p["name"], p["id"], ""))
        elif desc:
            if desc in seen_desc:
                out.append(("Pages '%s' and '%s' have the same description."
                            % (seen_desc[desc], p["name"]), p["id"], ""))
            seen_desc.setdefault(desc, p["name"])
            if len(desc) > 160:
                out.append(("The description of '%s' is over 160 characters." % p["name"], p["id"], ""))
        if len(title) > 60:
            out.append(("The title of '%s' is over 60 characters." % p["name"], p["id"], ""))
        if title in seen_title:
            out.append(("Pages '%s' and '%s' have the same title." % (seen_title[title], p["name"]),
                        p["id"], ""))
        seen_title.setdefault(title, p["name"])
        if not any(i.get("htag") == "h1" for i in p["items"] + doc.master_items(p)):
            out.append(("Page '%s' has no main heading (set a text box to Heading 1)." % p["name"],
                        p["id"], ""))
    if not seo.get("site_url"):
        out.append(("Add your site's web address in Search engine optimisation so a sitemap "
                    "and canonical links can be made.", "", ""))
        if getattr(doc, "feed", {}).get("enabled"):
            out.append(("A podcast feed needs the site's web address.", "", ""))
    return out
