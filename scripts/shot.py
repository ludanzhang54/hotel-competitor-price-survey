# -*- coding: utf-8 -*-
"""Render a local HTML file to a PNG, to check the layout by eye.

Usage:
  python shot.py board.html                       # writes board.png from the top
  python shot.py board.html --top 1200            # scroll to y=1200 first
  python shot.py board.html --out out.png --height 1000
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("html")
ap.add_argument("--out")
ap.add_argument("--top", type=int, default=0)
ap.add_argument("--height", type=int, default=900)
a = ap.parse_args()

html = Path(a.html)
out = Path(a.out) if a.out else html.with_suffix(".png")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": a.height})
    pg.goto(html.resolve().as_uri())
    pg.wait_for_timeout(1500)
    if a.top:
        pg.evaluate("y => window.scrollTo(0, y)", a.top)
        pg.wait_for_timeout(600)
    pg.screenshot(path=str(out))
    b.close()
print("SHOT", out)
