"""Compositions: groups of objects saved once and reused on any page or site."""
import json
import os
import re

from .model import asset_refs

FOLDER = os.path.expanduser("~/.local/share/sitewright/compositions")


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "composition"


def save(name, items, assets, folder=None):
    """items: object dicts already moved so the top-left is (0, 0).
    assets: {id: {name, data}} for every picture they use."""
    folder = folder or FOLDER
    os.makedirs(folder, exist_ok=True)
    used = {}
    for it in items:
        for a in asset_refs(it):
            if a in assets:
                used[a] = assets[a]
    base, n = _slug(name), 2
    path = os.path.join(folder, base + ".json")
    while os.path.exists(path):
        path = os.path.join(folder, "%s-%d.json" % (base, n))
        n += 1
    with open(path, "w") as f:
        json.dump(dict(name=name, items=items, assets=used), f)
    return path


def list_all(folder=None):
    folder = folder or FOLDER
    out = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".json"):
                p = os.path.join(folder, fn)
                try:
                    with open(p) as f:
                        out.append((json.load(f).get("name", fn[:-5]), p))
                except (OSError, ValueError):
                    continue
    return out


def load(path):
    with open(path) as f:
        return json.load(f)


def delete(path):
    try:
        os.remove(path)
    except OSError:
        pass
