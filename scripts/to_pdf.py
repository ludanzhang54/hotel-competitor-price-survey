# -*- coding: utf-8 -*-
"""Print the board HTML to PDF (the version you can send to an owner or a boss).

Usage:
  python to_pdf.py rate_board.html                 # writes rate_board.pdf next to it
  python to_pdf.py rate_board.html board_nov26.pdf
  python to_pdf.py --data-dir "<project folder>"   # finds the board in that folder

The board already carries print styles: the table header repeats on every page,
panels are not cut in half, background colours print, and hover-only text is hidden.
Requires: pip install playwright && playwright install chromium
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BOARD = "rate_board.html"


def pick(argv):
    html, out, data_dir = None, None, None
    it = iter(range(len(argv)))
    for i in it:
        a = argv[i]
        if a == "--data-dir" and i + 1 < len(argv):
            data_dir = Path(argv[i + 1])
            next(it, None)
        elif a.lower().endswith((".html", ".htm")):
            html = Path(a)
        elif a.lower().endswith(".pdf"):
            out = Path(a)
    if html is None:
        base = data_dir or Path.cwd()
        cand = base / BOARD
        if not cand.exists():
            hits = sorted(base.glob("*.html"))
            if not hits:
                raise SystemExit("No board HTML found; run make_board.py first")
            cand = hits[-1]
        html = cand
    if out is None:
        out = html.with_suffix(".pdf")
    return html, out


def main():
    html, out = pick(sys.argv[1:])
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(html.resolve().as_uri())
        pg.wait_for_timeout(1800)      # let the line chart finish drawing
        pg.pdf(path=str(out), format="A4", print_background=True,
               margin={"top": "10mm", "bottom": "10mm",
                       "left": "8mm", "right": "8mm"})
        b.close()
    print("PDF", out)


if __name__ == "__main__":
    main()
