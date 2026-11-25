# -*- coding: utf-8 -*-
"""Turn hotel names into the hotel list the collector needs (exact match only).

Usage:
  python ctrip_resolve.py --data-dir my_project --names "Hotel A name" "Hotel B name"
  python ctrip_resolve.py --data-dir my_project --file names.txt        # one name per line
  python ctrip_resolve.py --data-dir my_project --names "..." --append  # add to an existing list

Names can be the Ctrip Chinese name or the English name Ctrip shows. Chinese names work best.

Output:
  <data-dir>/ctrip_hotels.csv   hotel,hotel_id,city,city_id   (read by ctrip_collect.py)
  <data-dir>/hotels.csv         hotel,short_name              (read by make_board.py; edit the short names freely)

Rule: exact match only. If a name has no match, or several candidates, it is listed and
NOT written. Nothing is guessed. Fix the name (add the city, or use the English name) and
run again with --append.
"""
import argparse
import csv
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

API = ("https://m.ctrip.com/restapi/h5api/globalsearch/search?action=gsonline"
       "&source=globalonline&keyword={kw}&contentType=json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def search(kw):
    url = API.format(kw=urllib.parse.quote(kw))
    last = None
    for _ in range(2):  # one retry for a network hiccup, no more
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                data = json.load(r)
            return [x for x in (data.get("data") or []) if x.get("type") == "hotel"]
        except Exception as e:
            last = e
            time.sleep(1.2)
    raise RuntimeError("lookup failed: {} ({})".format(kw, last))


def norm(s):
    return "".join((s or "").lower().split())


def match(kw, hotels):
    if not hotels:
        return None, "no result"
    n = norm(kw)
    for h in hotels:
        if norm(h.get("word")) == n:
            return h, "exact (Chinese name)"
    for h in hotels:
        if norm(h.get("eName")) == n:
            return h, "exact (English name)"
    return None, "no exact name match ({} result(s)); not guessing".format(len(hotels))


def lcs_len(a, b):
    best, prev = 0, [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def related(kw, hotels):
    """Only show candidates that share a run of >= 4 characters with the query."""
    n = norm(kw)
    need = 4 if len(n) >= 4 else 2
    return [h for h in hotels
            if any(lcs_len(n, norm(x)) >= need for x in (h.get("word") or "", h.get("eName") or ""))]


def short_name(cn, city):
    s = cn
    if city and s.startswith(city):
        s = s[len(city):]
    for suf in ("大酒店", "酒店", "饭店", "宾馆"):
        if s.endswith(suf) and len(s) > len(suf) + 1:
            return s[: -len(suf)]
    return s or cn


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.getcwd())
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--file")
    ap.add_argument("--append", action="store_true")
    a = ap.parse_args()

    names = list(a.names)
    if a.file:
        with open(a.file, encoding="utf-8-sig") as f:
            names += [ln.strip() for ln in f if ln.strip()]
    names = [n.strip() for n in names if n and n.strip()]
    if not names:
        sys.exit('Give me hotel names: --names "A" "B" or --file names.txt')

    d = os.path.abspath(a.data_dir)
    os.makedirs(d, exist_ok=True)
    hp, sp = os.path.join(d, "ctrip_hotels.csv"), os.path.join(d, "hotels.csv")
    rows = read_csv(hp) if a.append else []
    # always keep short names you already edited, even without --append
    shorts = {r["hotel"]: r.get("short_name", "") for r in read_csv(sp)}
    if not a.append and rows == [] and os.path.exists(hp):
        print("Note: replacing the existing list (use --append to add instead). Your short names are kept.")
    seen = {r.get("hotel_id", "") for r in rows}
    bad = []

    for n_, kw in enumerate(names):
        if n_:
            time.sleep(random.uniform(0.5, 1.0))  # gentle on the lookup service
        try:
            hotels = search(kw)
        except RuntimeError as e:
            bad.append((kw, str(e)))
            print("  x {} -> {}".format(kw, e))
            continue
        hit, why = match(kw, hotels)
        if not hit:
            bad.append((kw, why))
            print("  x {} -> {}".format(kw, why))
            cand = related(kw, hotels)
            for h in cand[:6]:
                print("       candidate: {} (id={}, {}, cityId={})".format(
                    h.get("word"), h.get("id"), h.get("cityName"), h.get("cityId")))
            if hotels and not cand:
                print("       ({} results found, none look related. Do not force a match.)".format(len(hotels)))
            continue
        hid = str(hit["id"])
        if hid in seen:
            print("  = {} -> already in the list".format(hit.get("word")))
            continue
        seen.add(hid)
        city = hit.get("cityName") or ""
        cn = hit.get("word", "")
        rows.append({"hotel": cn, "hotel_id": hid, "city": city, "city_id": hit.get("cityId", "")})
        shorts.setdefault(cn, short_name(cn, city))
        print("  ok {} -> {} ({}, cityId={}, {})".format(kw, cn, city, hit.get("cityId"), why))

    write_csv(hp, ["hotel", "hotel_id", "city", "city_id"], rows)
    write_csv(sp, ["hotel", "short_name"], [{"hotel": r["hotel"], "short_name": shorts.get(r["hotel"], "")} for r in rows])
    print("\n{} hotels -> {}".format(len(rows), hp))
    if bad:
        print("\nNot resolved (not written):")
        for kw, why in bad:
            print("  - {}: {}".format(kw, why))
        print("Fix the names (add the city, or use the English name) and run again with --append.")
        sys.exit(2)


if __name__ == "__main__":
    main()
