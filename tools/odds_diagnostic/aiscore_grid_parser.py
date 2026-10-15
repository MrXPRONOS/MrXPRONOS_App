"""Extract visible AiScore corner triplets from text element rectangles without assuming HTML <table>."""
import re

NUM = re.compile(r"^\d{1,2}[.,]5$")
PRICE = re.compile(r"^\d{1,2}[.,]\d{2,3}$")

def extract_corner_grid(nodes, max_rows=12):
    """
    nodes: [{"text": str, "x": float, "y": float}] for displayed leaf elements.
    Locate adjacent Corners/Over/Under headers on same y, and triplets below.
    Returns only plausible, horizontally aligned triplets, not goal prices.
    """
    def clean(s):
        return str(s or "").strip().lower().replace(",", ".")
    headers = [n for n in nodes if clean(n.get("text")) in ("corners", "corner")]
    quotes = []
    for h in headers:
        hx,hy = h.get("x",0),h.get("y",0)
        overs = [n for n in nodes if clean(n.get("text")) == "over"
                 and 25 < n.get("x",0)-hx < 175 and abs(n.get("y",0)-hy) < 22]
        for over in overs:
            ox = over["x"]
            unders = [n for n in nodes if clean(n.get("text")) == "under"
                      and 25 < n.get("x",0)-ox < 175 and abs(n.get("y",0)-hy) < 22]
            for under in unders:
                ux=under["x"]
                x1tol=min(42, (ox-hx)*0.43)
                x2tol=min(42, (ux-ox)*0.43)
                lines=[n for n in nodes if NUM.fullmatch(clean(n.get("text")))
                       and abs(n.get("x",0)-hx) < x1tol and 12 < n.get("y",0)-hy < 550]
                for line in lines:
                    liney = line["y"]
                    matching_over=[n for n in nodes if PRICE.fullmatch(clean(n.get("text")))
                              and abs(n.get("x",0)-ox) < min(x1tol,x2tol)
                              and abs(n.get("y",0)-liney) < 16]
                    matching_under=[n for n in nodes if PRICE.fullmatch(clean(n.get("text")))
                              and abs(n.get("x",0)-ux) < x2tol
                              and abs(n.get("y",0)-liney) < 16]
                    if not matching_over or not matching_under:
                        continue
                    ln=float(clean(line["text"]))
                    ov=float(clean(matching_over[0]["text"]))
                    un=float(clean(matching_under[0]["text"]))
                    if not (1.01 <= ov <= 100 and 1.01 <= un <= 100):
                        continue
                    quote={"total_corners":ln,"over":ov,"under":un}
                    if quote not in quotes:
                        quotes.append(quote)
                    if len(quotes)>=max_rows: return quotes
            if quotes:return sorted(quotes,key=lambda q:q["total_corners"])
    return sorted(quotes,key=lambda q:q["total_corners"])
