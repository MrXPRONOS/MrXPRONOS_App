"""Read AiScore's actual div.table.corner rows by phase, without mistaking goals for corners."""
from html.parser import HTMLParser
import re

_PHASE_COLORS = {"#2196f3": "opening", "#ffba5a": "prematch", "#5db400": "in_play"}
_LINE = re.compile(r"^(?:\d{1,2}(?:[.,][05]))$")
_PRICE = re.compile(r"^\d{1,2}[.,]\d{2,3}$")


def parse_corner_rows(rows):
    """Parse DOM-extracted corner rows, retaining opening/prematch/in-play semantics."""
    result = []
    for row in rows:
        style = str(row.get("style", "")).lower().replace(" ", "")
        phase = next((label for color, label in _PHASE_COLORS.items() if color in style), "unknown")
        columns = [str(x).strip().replace(",", ".") for x in row.get("values", [])]
        if len(columns) != 3:
            continue
        line, over, under = columns
        if not _LINE.fullmatch(line) or not (_PRICE.fullmatch(over) and _PRICE.fullmatch(under)):
            continue
        if not (1.01 <= float(over) <= 100 and 1.01 <= float(under) <= 100):
            continue
        quote = {"phase": phase, "total_corners": float(line), "over": float(over), "under": float(under)}
        if quote not in result:
            result.append(quote)
    return result


class _CornersHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.corner_rows = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        props = dict(attrs)
        classes = set(props.get("class", "").split())
        in_corner = any(node["corner"] for node in self.stack)
        active_row = next((node["row"] for node in reversed(self.stack) if node["row"] is not None), None)
        is_row = bool(in_corner and {"row", "box"} <= classes and active_row is None)
        is_col = bool(active_row is not None and "col" in classes and not any(node["column"] is not None for node in self.stack))
        self.stack.append({
            "corner": bool({"table", "corner"} <= classes),
            "row": {"style": props.get("style", ""), "values": []} if is_row else None,
            "column": [] if is_col else None,
        })

    def handle_endtag(self, tag):
        if tag != "div" or not self.stack:
            return
        node = self.stack.pop()
        if node["column"] is not None:
            current_row = next((item["row"] for item in reversed(self.stack) if item["row"] is not None), None)
            if current_row is not None:
                current_row["values"].append("".join(node["column"]).strip())
        if node["row"] is not None:
            self.corner_rows.append(node["row"])

    def handle_data(self, data):
        for node in reversed(self.stack):
            if node["column"] is not None:
                node["column"].append(data)
                break


def extract_corner_odds_from_html(html):
    """Deterministic offline verification against supplied AiScore HTML snapshots."""
    parser = _CornersHTMLParser()
    parser.feed(html)
    parser.close()
    return parse_corner_rows(parser.corner_rows)
