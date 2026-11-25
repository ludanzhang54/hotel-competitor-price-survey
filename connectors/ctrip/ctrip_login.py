# -*- coding: utf-8 -*-
"""Log in to Ctrip yourself in a visible browser and save the session for the collector.

Usage:
  python ctrip_login.py --data-dir my_project

A browser window opens. Log in by hand. Come back to this terminal and press Enter.
The session (cookies) is saved to <data-dir>/ctrip_state.json.

Your password is never typed by this script and is never stored. The session file is
as sensitive as a password: do not commit it, do not share it. Ctrip may restrict an
account that makes many searches in a short time, so consider using a separate account.
"""
import argparse
import os

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default=os.getcwd())
ap.add_argument("--state-file")
a = ap.parse_args()
state = a.state_file or os.path.join(os.path.abspath(a.data_dir), "ctrip_state.json")
os.makedirs(os.path.dirname(state), exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    ctx = b.new_context(locale="zh-CN", viewport={"width": 1280, "height": 860})
    pg = ctx.new_page()
    pg.goto("https://hotels.ctrip.com/")
    input("Log in in the browser window, then press Enter here to save the session... ")
    ctx.storage_state(path=state)
    b.close()
try:
    os.chmod(state, 0o600)
except OSError:
    pass
print("Saved session to", state)
