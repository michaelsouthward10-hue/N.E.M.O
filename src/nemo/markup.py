"""Render simple chat Markdown, retaining the visible text for citation offsets."""
import re


def render(widget, message):
    widget.tag_configure("md-heading", font=("Segoe UI", 13, "bold"), spacing1=8)
    widget.tag_configure("md-bold", font=("Segoe UI", 11, "bold"))
    visible = []
    for line in message.splitlines(keepends=True):
        heading = re.match(r"^#{1,6}\s+", line)
        if heading:
            line = line[heading.end():]
        else:
            line = re.sub(r"^(\s*)[-*] ", r"\1• ", line)
        for part in re.split(r"(\*\*[^\n]+?\*\*)", line):
            bold = part.startswith("**") and part.endswith("**") and len(part) > 4
            text = part[2:-2] if bold else part
            tags = ("message", "md-heading") if heading else ("message", "md-bold") if bold else ("message",)
            widget.insert("end", text, tags)
            visible.append(text)
    return "".join(visible)
