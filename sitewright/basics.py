"""Small things shared by the document model and the web-app objects (kept apart so neither imports the other)."""
import uuid

TEXT_BASE = dict(font="Sans Serif", size=18, color="#222222", bold=False, italic=False, align="left")


def new_id():
    return uuid.uuid4().hex[:10]
