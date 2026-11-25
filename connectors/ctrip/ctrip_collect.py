# -*- coding: utf-8 -*-
"""Collect the lowest bookable Ctrip price for a hotel list and save one archive file.

This collector targets the Ctrip mainland (Chinese-language) hotel list page.
Read docs/CHANNELS.md section 2 before you use it.

Usage:
  python ctrip_collect.py --data-dir my_project                 # hotels x next 30 days
  python ctrip_collect.py --data-dir my_project --probe         # first 3 stay dates only
  python ctrip_collect.py --data-dir my_project --days 14
  python ctrip_collect.py --data-dir my_project --dates 2026-12-24,2026-12-31   # chosen dates only
  python ctrip_collect.py --data-dir my_project --headful       # show the browser, for debugging

Inputs:
  <data-dir>/ctrip_hotels.csv   columns: hotel,hotel_id,city,city_id   (see ctrip_resolve.py)
  <data-dir>/ctrip_state.json   your own login session (see ctrip_login.py). Never commit this file.

Output:
  <data-dir>/archive/run_YYYY-MM-DD_HHMMSS.csv   columns as in docs/DATA_FORMAT.md

Rules this script follows:
  - Default search only: 1 room, 1 night, 1 adult. Lowest bookable price shown.
  - A verification (slider) page stops the whole run. It is never bypassed or retried.
  - "sold out" and "no price" are recorded as different statuses. Nothing is ever filled in.
"""
import argparse
import asyncio
import csv
import json
import os
import random
import sys
from datetime import date, datetime, timedelta
from urllib.parse import quote

from playwright.async_api import async_playwright

FIELDS = ["captured_at", "hotel", "channel", "stay_date", "price", "currency", "status"]

BASE = (
    "https://hotels.ctrip.com/hotels/list?flexType=1&fixedDate=0"
    "&cityId={cid}&provinceId=0&countryId=1"
    "&cityName={cn}&destName={cn}"
    "&searchWord={kw}&searchType=&checkin={ci}&checkout={co}"
    "&crn=1&listFilters=29~1*29*1~1*2&curr=CNY&locale=zh-CN"
    "&directSearch=1&old=1&v2_mod=80&v2_version=E"
)

# Runs inside the page: wait for prices, then read the first "from <price>" in the exact-match block.
# The page text is Chinese, so the patterns below are Chinese on purpose.
EXTRACT_JS = r"""
async () => {
  const kw = __KW__;
  const deadline = Date.now() + 12000;
  let t = '';
  while (Date.now() < deadline) {
    t = document.body.innerText || '';
    if (t.includes('验证') && (t.includes('滑块') || t.includes('拖动'))) {
      return {status:'blocked'};
    }
    if (/找到\s*\d+\s*家酒店/.test(t) && /¥[\d,]+\s*起/.test(t)) break;
    await new Promise(r => setTimeout(r, 300));
  }
  const i = t.indexOf('找到');
  if (i < 0) return {status:'no_result'};
  const found = (t.slice(i, i + 30).match(/找到\s*(\d+)\s*家酒店/) || [])[1];
  const j = t.indexOf('以上是符合条件');
  const block = t.slice(i, j > i ? j : i + 900);
  if (found !== '1' || !block.includes(kw)) return {status:'not_exact', found:found};
  const m = block.match(/¥([\d,]+)\s*起/);
  if (!m) return {status: /售罄/.test(block) ? 'soldout' : 'no_price'};
  return {status:'ok', price: parseInt(m[1].replace(/,/g, ''), 10)};
}
"""


def load_hotels(data_dir):
    path = os.path.join(data_dir, "ctrip_hotels.csv")
    if not os.path.exists(path):
        sys.exit("Hotel list not found: " + path + " (create it with ctrip_resolve.py)")
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = (r.get("hotel") or "").strip()
            if not name:
                continue
            if not (r.get("city_id") or "").strip():
                sys.exit("Hotel '{}' has no city_id; run ctrip_resolve.py again".format(name))
            out.append({"name": name, "id": (r.get("hotel_id") or "").strip(),
                        "city": (r.get("city") or "").strip(), "cid": r["city_id"].strip()})
    if not out:
        sys.exit("The hotel list is empty")
    return out


def build_url(h, ci, co):
    return BASE.format(cid=h["cid"], cn=quote(h["city"]), kw=quote(h["name"]),
                       ci=ci.isoformat(), co=co.isoformat())


def stay_dates(args):
    if args.dates:
        try:
            return [date.fromisoformat(x.strip()) for x in args.dates.split(",") if x.strip()]
        except ValueError:
            sys.exit("--dates must look like 2026-12-24,2026-12-31")
    n = 3 if args.probe else args.days
    today = date.today()
    return [today + timedelta(days=i) for i in range(n)]


async def collect(args):
    data_dir = os.path.abspath(args.data_dir)
    hotels = load_hotels(data_dir)
    state = args.state_file or os.path.join(data_dir, "ctrip_state.json")
    if not os.path.exists(state):
        sys.exit("No login session at " + state + ". Run ctrip_login.py first.")
    archive = os.path.join(data_dir, "archive")
    os.makedirs(archive, exist_ok=True)
    dates = stay_dates(args)

    rows, blocked, stale = [], False, False
    started = datetime.now()
    bad_streak = 0
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=not args.headful)
            ctx = await browser.new_context(storage_state=state,
                                            viewport={"width": 1440, "height": 900},
                                            locale="zh-CN")
            page = await ctx.new_page()
            try:
                total, n = len(hotels) * len(dates), 0
                for h in hotels:
                    if blocked or stale:
                        break
                    for d in dates:
                        n += 1
                        co = d + timedelta(days=1)
                        try:
                            await page.goto(build_url(h, d, co),
                                            wait_until="domcontentloaded", timeout=30000)
                            res = await page.evaluate(
                                EXTRACT_JS.replace("__KW__", json.dumps(h["name"], ensure_ascii=False)))
                            if "login" in page.url.lower() or "passport" in page.url.lower():
                                res = {"status": "login_page"}
                        except Exception as e:
                            res = {"status": "error", "msg": str(e)[:120]}
                        st = res.get("status")
                        print("[{}/{}] {} {} -> {} {}".format(
                            n, total, h["name"], d, st, res.get("price", "")), flush=True)
                        if st == "blocked":
                            # A verification page appeared. Stop. Do not bypass, retry or switch network.
                            # This page is not a price reading, so it is not written to the archive.
                            print("VERIFICATION PAGE: run stopped. Solve it by hand in a visible "
                                  "browser, wait, then run again with fewer hotels or dates.", flush=True)
                            blocked = True
                            break
                        rows.append({"hotel": h["name"], "stay_date": d.isoformat(),
                                     "price": res.get("price", ""), "status": st})
                        # a stale session shows up as a login page or many empty pages in a row
                        bad_streak = bad_streak + 1 if st in ("login_page", "no_result", "error") else 0
                        if st == "login_page" or bad_streak >= 5:
                            print("SESSION LOOKS STALE: stopping. Run ctrip_login.py again.", flush=True)
                            stale = True
                            break
                        await page.wait_for_timeout(random.randint(700, 1400))
            finally:
                await browser.close()
    finally:
        # also runs on Ctrl-C or a crash, so rows already collected are not lost
        if rows:
            incomplete = blocked or stale or len(rows) < len(hotels) * len(dates)
            name = "run_{}.csv".format(started.strftime("%Y-%m-%d_%H%M%S"))
            out = os.path.join(archive, name)
            stamp = started.strftime("%Y-%m-%d %H:%M:%S")   # run start time, same for every row
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                for r in rows:
                    status = {"ok": "ok", "soldout": "soldout"}.get(r["status"], "no_price")
                    w.writerow({"captured_at": stamp, "hotel": r["hotel"], "channel": "Ctrip",
                                "stay_date": r["stay_date"], "price": r["price"],
                                "currency": "CNY", "status": status})
            print("ARCHIVE", out, flush=True)
            if incomplete:
                print("NOTE: this run is incomplete (stopped early or a chosen subset). The board will "
                      "show only what it contains and will warn you.", flush=True)
    return rows, blocked


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.getcwd(), help="project folder")
    ap.add_argument("--days", type=int, default=30, help="stay dates from today (default 30)")
    ap.add_argument("--dates", help="comma-separated stay dates, e.g. 2026-12-24,2026-12-31")
    ap.add_argument("--probe", action="store_true", help="first 3 stay dates only")
    ap.add_argument("--headful", action="store_true", help="show the browser window")
    ap.add_argument("--state-file", help="login session file (default <data-dir>/ctrip_state.json)")
    a = ap.parse_args()
    rows, blocked = asyncio.run(collect(a))
    ok = sum(1 for r in rows if r["price"] != "")
    sold = sum(1 for r in rows if r["status"] == "soldout")
    print("RESULT ok={}/{} soldout={} blocked={}".format(ok, len(rows), sold, blocked))
