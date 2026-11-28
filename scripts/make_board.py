# -*- coding: utf-8 -*-
"""Render the archive of price runs into one board: you vs the comp set.

Usage:
    python make_board.py --data-dir "<project folder>" [--home "your hotel"]

Input  : <project folder>/archive/run_*.csv   (see docs/DATA_FORMAT.md)
Optional: <project folder>/hotels.csv        (hotel, short_name)
Output : <project folder>/rate_board.html

Your hotel only needs to be given once; it is saved to home.txt and reused.
Without one, the board runs as an equal-weight scan of all hotels.
The board shows data only. It never writes conclusions.
"""
import csv
import json
import os
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.getcwd()
CMP = os.path.join(DATA, "latest_comparison.csv")
HOTELS_CSV = os.path.join(DATA, "hotels.csv")
HOME_TXT = os.path.join(DATA, "home.txt")
OUT = os.path.join(DATA, "rate_board.html")


def set_data_dir(p):
    """Switch the project folder: hotel list, archive and board follow."""
    global DATA, CMP, HOTELS_CSV, HOME_TXT, OUT
    DATA = os.path.abspath(p)
    CMP = os.path.join(DATA, "latest_comparison.csv")
    HOTELS_CSV = os.path.join(DATA, "hotels.csv")
    HOME_TXT = os.path.join(DATA, "home.txt")
    OUT = os.path.join(DATA, "rate_board.html")


WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CAP = None           # optional absolute cap (--cap N): any price above it is a high-price room type. Default: 10000 when the archive currency is CNY (Ctrip), otherwise off
SUITE_RATIO = 2.5    # multiple of the hotel’s own median above which a price is a high-price room type
MIN_DAYS = 10        # with fewer normal-price days than this, the relative rule is not applied (only --cap, if set)
BAR_SPAN = 20        # fixed bar scale: full bar = +/-20%, the same every run so boards can be compared

HOME_COLOR = "#2f6fed"
COMP_COLORS = ["#e8710a", "#188038", "#c5221f", "#8a3ffc", "#0f9bb5",
               "#a8742a", "#b80074", "#5c7a00", "#0b6b4f", "#8c2f39"]

SHORT = {}


def load_short():
    """Short names come from the optional short_name column of hotels.csv."""
    SHORT.clear()
    if not os.path.exists(HOTELS_CSV):
        return
    with open(HOTELS_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            h = (r.get("hotel") or "").strip()
            sn = (r.get("short_name") or "").strip()
            if h:
                SHORT[h] = sn or h


def short(h):
    return SHORT.get(h, h)


def dy(n):
    """'1 day' / '3 days'."""
    return "{} day{}".format(n, "" if n == 1 else "s")


def money(v):
    return "{:,}".format(int(round(v)))


def med_of(vals):
    """Median. For an even count, the mean of the two middle values."""
    s = sorted(vals)
    n = len(s)
    if not n:
        return None
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def pct(a, b):
    """How many percent a is above b (positive = above)."""
    if not b:
        return None
    return (a - b) / b * 100


def resolve_home(arg, hotels):
    """Your hotel: command line first, then home.txt. Full or short name both work; if not found, run without one."""
    want = (arg or "").strip()
    if not want and os.path.exists(HOME_TXT):
        want = open(HOME_TXT, encoding="utf-8").read().strip()
    if not want:
        return None
    for h in hotels:
        if h == want:
            return h
    for h in hotels:
        if short(h) == want:
            return h
    for h in hotels:
        if want in h or (short(h) and short(h) in want):
            return h
    print("WARNING: hotel '{}' not found; running without a home hotel. Available: {}".format(
        want, "; ".join(hotels)))
    return None


def sparkline(vals, color, lo, hi, w=66, h=22, width=1.8):
    """Mini trend line. All hotels share one vertical scale (lo/hi passed in) so a column can be compared."""
    pts = [v for v in vals if v is not None]
    if len(pts) < 2 or hi <= lo:
        return '<span class="sp"></span>'
    n = max(len(vals) - 1, 1)
    d, pen = "", False
    for i, v in enumerate(vals):
        if v is None:
            pen = False
            continue
        x = i / n * w
        y = (h - 3) - (v - lo) / (hi - lo) * (h - 6)
        d += ("L" if pen else "M") + "{:.1f},{:.1f} ".format(x, y)
        pen = True
    return ('<svg class="sp" viewBox="0 0 {} {}" width="{}" height="{}">'
            '<path d="{}" fill="none" stroke="{}" stroke-width="{}" '
            'stroke-linejoin="round" stroke-linecap="round"/></svg>').format(
        w, h, w, h, d.strip(), color, width)


def read_archive(path):
    """One archive file -> {(hotel, stay_date): (price or None, status)}"""
    out = {}
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        miss = [c for c in ("hotel", "stay_date", "price") if c not in (rd.fieldnames or [])]
        if miss:
            raise SystemExit("{}: missing column(s) {} (see docs/DATA_FORMAT.md)".format(path, ", ".join(miss)))
        for n, r in enumerate(rd, 2):
            v = (r.get("price") or "").strip()
            for ch in ",¥$€£ ":
                v = v.replace(ch, "")
            try:
                price = int(float(v)) if v else None
            except ValueError:
                raise SystemExit("{} line {}: cannot read price '{}'".format(path, n, r.get("price")))
            out[(r["hotel"].strip(), r["stay_date"].strip())] = (price, (r.get("status") or "").strip())
    return out


def archive_stamp(path):
    """Collection time of an archive file, as 'YYYY-MM-DD HH:MM'."""
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8-sig") as f:
        first = next(csv.DictReader(f), None)
    s = ((first or {}).get("captured_at") or "").strip()
    return s[:16]


def archive_files(arch):
    if not os.path.isdir(arch):
        return []
    return sorted(os.path.join(arch, f) for f in os.listdir(arch)
                  if f.startswith("run_") and f.endswith(".csv"))


def archive_currency(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8-sig") as f:
        first = next(csv.DictReader(f), None)
    return ((first or {}).get("currency") or "").strip()


def build_comparison(arch):
    """Latest run vs the previous run -> one row per (hotel, stay_date)."""
    files = archive_files(arch)
    if not files:
        raise SystemExit("No run_*.csv files in " + arch + " (see docs/DATA_FORMAT.md)")
    cur, prev = read_archive(files[-1]), (read_archive(files[-2]) if len(files) > 1 else {})
    rows = []
    for (h, d), (price, status) in cur.items():
        old = prev.get((h, d), (None, ""))[0]
        r = {"hotel": h, "stay_date": d, "curr": str(price) if price is not None else "",
             "prev": str(old) if old is not None else "", "status": status,
             "diff": "", "dir": ""}
        if price is not None and old is not None:
            dv = price - old
            r["diff"] = str(dv)
            r["dir"] = "up" if dv > 0 else ("down" if dv < 0 else "same")
        rows.append(r)
    rows.sort(key=lambda r: (r["hotel"], r["stay_date"]))
    return rows


def load_optional(data_dir):
    """Optional inputs. Missing files are fine; the board just leaves those parts out.
    occupancy.csv: date,occupancy      (your own hotel, percent, e.g. 83 or 83%)
    events.csv:    date,event[,end_date]   (city events; end_date makes a range)
    """
    occ, ev = {}, {}
    p = os.path.join(data_dir, "occupancy.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d = (r.get("date") or "").strip()
                v = (r.get("occupancy") or "").strip().rstrip("%").strip()
                try:
                    occ[d] = float(v)
                except ValueError:
                    pass
    p = os.path.join(data_dir, "events.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d = (r.get("date") or "").strip()
                name = (r.get("event") or "").strip()
                e = (r.get("end_date") or "").strip() or d
                if not d or not name:
                    continue
                try:
                    a, b = date.fromisoformat(d), date.fromisoformat(e)
                except ValueError:
                    continue
                k = a
                while k <= b and (k - a).days < 60:
                    ev.setdefault(k.isoformat(), []).append(name)
                    k += timedelta(days=1)
    return occ, ev


def pretty_stamp(s):
    """2026-11-11 14:16 -> Nov 11 14:16"""
    try:
        d, t = s.split(" ")
        y, m, dd = d.split("-")
        return "{} {} {}".format(MON[int(m) - 1], int(dd), t)
    except Exception:
        return s


def gap_text(a, b):
    """How long between two runs, in plain words."""
    try:
        t1 = datetime.strptime(a, "%Y-%m-%d %H:%M")
        t0 = datetime.strptime(b, "%Y-%m-%d %H:%M")
    except Exception:
        return ""
    sec = (t1 - t0).total_seconds()
    if sec <= 0:
        return ""
    hrs = sec / 3600
    if hrs < 1:
        return "{:.0f} minutes apart".format(sec / 60)
    if hrs < 48:
        return "{:.0f} hours apart".format(hrs)
    return "{:.1f} days apart".format(hrs / 24)


def main(home_arg=None):
    global CAP
    load_short()
    arch = os.path.join(DATA, "archive")
    files = archive_files(arch)
    rows = build_comparison(arch)
    currency = archive_currency(files[-1]) if files else ""
    if CAP is None and currency.upper() == "CNY":
        CAP = 10000   # Ctrip boards are in CNY: above 10,000 is always a high-price room type (suites)
    occ, events = load_optional(DATA)

    # only draw hotels on the watch list, when hotels.csv exists
    watch = []
    if os.path.exists(HOTELS_CSV):
        with open(HOTELS_CSV, encoding="utf-8-sig") as f:
            watch = [(r.get("hotel") or "").strip() for r in csv.DictReader(f)]
            watch = [x for x in watch if x]
    all_rows = rows
    if watch:
        rows = [r for r in rows if r["hotel"] in watch]
    if not rows:
        raise SystemExit("None of the hotels in hotels.csv appear in the latest run file. "
                         "Check that the names match the 'hotel' column exactly, or delete hotels.csv.")
    coverage_warn = ""
    if len(files) > 1:
        pv = read_archive(files[-2])
        cur_h = {r["hotel"] for r in all_rows}
        cur_d = {r["stay_date"] for r in all_rows}
        miss_h = sorted({h for h, _ in pv} - cur_h)
        miss_d = len({d for _, d in pv} - cur_d)
        if miss_h or miss_d:
            coverage_warn = ("The latest run covers fewer hotels or dates than the previous one "
                             "({} hotel(s), {} date(s) missing). It may have stopped early or been a partial refresh. "
                             "The board shows only what the latest run contains.").format(len(miss_h), miss_d)
            print("WARNING:", coverage_warn)

    hotels, dates, data = [], [], {}
    for r in rows:
        if r["hotel"] not in hotels:
            hotels.append(r["hotel"])
        if r["stay_date"] not in dates:
            dates.append(r["stay_date"])
        data[(r["hotel"], r["stay_date"])] = r
    dates.sort()

    # --- your hotel ---
    home = resolve_home(home_arg, hotels)
    if home:
        try:
            open(HOME_TXT, "w", encoding="utf-8").write(home)
        except Exception:
            pass
        hotels = [home] + [h for h in hotels if h != home]
    comps = [h for h in hotels if h != home]
    COLORS = ([HOME_COLOR] if home else []) + [
        COMP_COLORS[i % len(COMP_COLORS)] for i in range(len(comps))]
    cidx = {h: COLORS[i] for i, h in enumerate(hotels)}

    # --- two runs: timestamps and the previous run cell by cell ---
    stamp = archive_stamp(files[-1]) if files else ""
    prev_stamp = archive_stamp(files[-2]) if len(files) > 1 else ""
    prev = read_archive(files[-2]) if len(files) > 1 else {}
    d0, d1 = (dates[0], dates[-1]) if dates else ("", "")

    # --- raw series ---
    raw = {}
    for h in hotels:
        arr = []
        for d in dates:
            r = data.get((h, d))
            v = r["curr"] if r else ""
            arr.append(int(v) if v else None)
        raw[h] = arr

    # --- high-price room type detection (relative rule) ---
    # A price above SUITE_RATIO times the hotel’s own median is treated as a high-price room type.
    # Compared with the hotel itself only, never with other hotels on the same day, so one price is always treated the same way.
    # CAP is an absolute fallback; with fewer than MIN_DAYS normal days the median is unreliable, so only CAP is used.
    base_med = {h: med_of([v for v in raw[h] if v and (CAP is None or v <= CAP)]) for h in hotels}
    norm_days = {h: len([v for v in raw[h] if v and (CAP is None or v <= CAP)]) for h in hotels}

    def was_suite(h, v):
        """Is this price a high-price room type for this hotel? The previous run uses the same rule."""
        if not v:
            return False
        if CAP is not None and v > CAP:
            return True
        bm = base_med.get(h)
        return bool(bm and norm_days.get(h, 0) >= MIN_DAYS and v >= bm * SUITE_RATIO)

    suite = {h: [was_suite(h, raw[h][i]) for i in range(len(dates))] for h in hotels}
    # normal-price series: high-price days are blanked; charts, medians and ranks use it
    series = {h: [(None if suite[h][i] else raw[h][i]) for i in range(len(dates))]
              for h in hotels}
    suite_n = sum(1 for h in hotels for x in suite[h] if x)

    def val(h, d):
        return series[h][dates.index(d)] if d in dates else None

    didx = {d: i for i, d in enumerate(dates)}

    # --- per day: competitor median (excluding you), each hotel’s median, rank ---
    # One rule for the whole page: the median. A mean is pulled by one extreme price; a median is not.
    comp_med, comp_n, day_med, day_n = {}, {}, {}, {}
    rank_hist = {h: [] for h in hotels}
    soldout_n, soldout_who = {}, {}
    for d in dates:
        i = didx[d]
        vs = {h: series[h][i] for h in hotels if series[h][i]}
        day_n[d] = len(vs)
        if len(vs) >= 2:
            day_med[d] = med_of(list(vs.values()))
            for k, (h, _v) in enumerate(sorted(vs.items(), key=lambda x: x[1]), 1):
                rank_hist[h].append(k)
        cv = [series[h][i] for h in comps if series[h][i]]
        comp_n[d] = len(cv)
        if len(cv) >= 2:
            comp_med[d] = med_of(cv)
        who = [h for h in hotels
               if (data.get((h, d)) or {}).get("status") == "soldout"]
        soldout_n[d] = len(who)
        soldout_who[d] = who

    avg_rank = {h: (sum(rank_hist[h]) / len(rank_hist[h]) if rank_hist[h] else None)
                for h in hotels}
    cheap_days = {h: sum(1 for k in rank_hist[h] if k == 1) for h in hotels}

    # --- per hotel: window median, and the median of the other hotels (leave-one-out) ---
    # Both numbers are on the page; each percentage is simply one divided by the other, so anyone can check it.
    stat = {h: sorted([v for v in series[h] if v]) for h in hotels}
    med = {h: med_of(stat[h]) for h in hotels}
    live = [h for h in hotels if med[h]]
    N = len(live)

    other_med, lo_pct = {}, {}
    for h in hotels:
        dms = []
        for d in dates:
            i = didx[d]
            others = [series[o][i] for o in hotels if o != h and series[o][i]]
            if len(others) >= 2:
                dms.append(med_of(others))
        other_med[h] = med_of(dms) if dms else None
        lo_pct[h] = (pct(med[h], other_med[h])
                     if (med[h] and other_med[h]) else None)

    # --- how often each hotel changed its price ---
    moved_days, price_steps = {}, {}
    for h in hotels:
        mv = sum(1 for r in rows if r["hotel"] == h and r.get("dir") in ("up", "down"))
        moved_days[h] = mv
        price_steps[h] = len({v for v in series[h] if v})

    # --- sold-out days ---
    sold_days = {h: sum(1 for d in dates
                        if (data.get((h, d)) or {}).get("status") == "soldout")
                 for h in hotels}

    ok = sum(1 for r in rows if r["curr"])
    soldout_total = sum(1 for r in rows if r.get("status") == "soldout")

    # ================= panel 1: where you stand =================
    def tile(big, label, cls=""):
        return ('<div class="tile"><div class="tb {}">{}</div>'
                '<div class="tl">{}</div></div>').format(cls, big, label)

    if home and med[home]:
        hp = lo_pct[home]
        gap_cls = "up" if (hp or 0) > 0.5 else ("down" if (hp or 0) < -0.5 else "")
        gap_big = ("—" if hp is None else
                   "{:.0f}% above".format(hp) if hp > 0.5 else
                   ("{:.0f}% below".format(-hp) if hp < -0.5 else "About the same"))
        cm = other_med[home]
        tiles = (
            tile(money(med[home]), "Your median price") +
            tile(money(cm) if cm else "—", "Comp-set median ({} hotel{})".format(len(comps), "" if len(comps) == 1 else "s")) +
            tile(gap_big, "You vs comp set", gap_cls) +
            tile("{} / {}".format(dy(cheap_days[home]), dy(sold_days[home])),
                 "Days you are cheapest / days sold out")
        )
        homepanel = ('<div class="panel"><h2>Where you stand now'
                     '<span class="h2sub">{} competitor{} · definitions in the footer</span></h2>'
                     '<div class="tiles">{}</div></div>\n').format(len(comps), "" if len(comps) == 1 else "s", tiles)
    else:
        homepanel = ""

    # ================= panel 2: what changed since the previous run =================
    def dlabel(d):
        y, m, dd = d.split("-")
        w = WEEK[date(int(y), int(m), int(dd)).weekday()]
        return "{} {} {}".format(w, MON[int(m) - 1], int(dd))

    def dshort(d):
        _y, m, dd = d.split("-")
        return "{}/{}".format(int(m), int(dd))

    def hlabel(h):
        """Your hotel is labelled simply "You", with no hotel name."""
        return '<i class="meh">You</i>' if h == home else short(h)

    newsold, reopen, moves = [], [], []
    for h in hotels:
        for d in dates:
            r = data.get((h, d))
            if not r:
                continue
            pv, ps = prev.get((h, d), (None, ""))
            now_sold = r.get("status") == "soldout"
            has_now = bool(r["curr"])
            if now_sold and pv:
                newsold.append((h, d, pv, was_suite(h, pv)))
            elif has_now and ps == "soldout":
                reopen.append((h, d, int(r["curr"])))
            diff = r.get("diff", "")
            if diff not in ("", None) and int(diff) != 0 and r["prev"]:
                i2 = didx.get(d)
                # if either end is a high-price room type the difference is meaningless; skip it
                if (i2 is not None and not suite[h][i2]
                        and not was_suite(h, int(r["prev"]))):
                    moves.append((h, d, int(r["prev"]), int(r["curr"]), int(diff)))

    if not prev:
        changepanel = ('<div class="panel"><h2>What changed since the previous run</h2>'
                       '<div class="note">This is the first run, so there is no previous run to compare.'
                       'After the next run this panel lists, by hotel, who changed price, who sold out and who reopened.</div></div>\n')
    else:
        crows = []
        for h in hotels:
            mv = [m for m in moves if m[0] == h]
            ups = sorted([m for m in mv if m[4] > 0], key=lambda m: -m[4])
            dns = sorted([m for m in mv if m[4] < 0], key=lambda m: m[4])
            ns = [x for x in newsold if x[0] == h]
            ro = [x for x in reopen if x[0] == h]

            def one(m, cls):
                return ('<b class="{}">{}{}</b><span class="when">{}</span>'.format(
                    cls, "+" if m[4] > 0 else "-", money(abs(m[4])), dshort(m[1])))

            crows.append(
                '<tr class="{me}"><th>{nm}</th>'
                '<td class="c">{n}</td>'
                '<td>{up}</td><td>{dn}</td>'
                '<td class="ev">{ns}</td><td class="ev">{ro}</td></tr>'.format(
                    me="me" if h == home else "", nm=hlabel(h),
                    n=dy(len(mv)) if mv else "—",
                    up=one(ups[0], "up") if ups else "—",
                    dn=one(dns[0], "down") if dns else "—",
                    ns="、".join(dshort(x[1]) for x in ns) if ns else "—",
                    ro="、".join(dshort(x[1]) for x in ro) if ro else "—"))

        g = gap_text(stamp, prev_stamp)
        changepanel = (
            '<div class="panel"><h2>What changed since the previous run'
            '<span class="h2sub">by hotel · previous run {}{}</span></h2>'
            '<table class="mini wide"><thead><tr><th>Hotel</th><th>Changes</th>'
            '<th>Biggest rise</th><th>Biggest drop</th><th>Newly sold out</th><th>Reopened</th>'
            '</tr></thead><tbody>{}</tbody></table>'
            '<div class="note">"Changes" = how many stay dates have a different price from the previous run. '
            'The rise and drop columns show the biggest single day; every change is in the small print of the daily table below. '
            'A change is ignored when either end is only a high-price room type.</div></div>\n').format(
            pretty_stamp(prev_stamp), " ({})".format(g) if g else "",
            "".join(crows))

    # ================= panel 4: position of each hotel =================
    allnorm = [v for h in hotels for v in series[h] if v]
    sp_lo, sp_hi = (min(allnorm), max(allnorm)) if allnorm else (0, 1)
    order = sorted(hotels, key=lambda x: (avg_rank[x] if avg_rank[x] else 99,
                                          med[x] if med[x] else 10 ** 9))
    prow = []
    for i2, h in enumerate(order, 1):
        ishome = (h == home)
        if not med[h]:
            prow.append('<div class="prow{}"><span class="rk">—</span>'
                        '<div class="hin"><span class="hname">{}</span>'
                        '<span class="hsub">sold out for the whole window</span></div>'
                        '<span class="sp"></span><div class="track"></div>'
                        '<span class="pv">—</span><span class="pi flat">—</span>'
                        '<span class="mvv">—</span></div>'.format(
                            " me" if ishome else "", hlabel(h)))
            continue
        vals = stat[h]
        gp = lo_pct[h]
        cls = "neg" if (gp or 0) < -0.5 else ("pos" if (gp or 0) > 0.5 else "flat")
        gap_txt = ("{:.0f}% below".format(-gp) if gp and gp < -0.5 else
                   ("{:.0f}% above".format(gp) if gp and gp > 0.5 else "")) if gp is not None else "—"
        out_n = sum(1 for x in suite[h] if x)
        sub = "{} ~ {} · cheapest {}".format(
            money(vals[0]), money(vals[-1]), dy(cheap_days[h]))
        dot = ('<i class="hdot" title="{} more days only had a suite or other high-price room type; excluded"></i>'
               .format(out_n)) if out_n else ""
        dev = gp or 0
        over = abs(dev) > BAR_SPAN
        bw = max(0.9, min(50.0, abs(dev) / BAR_SPAN * 50))
        barstyle = ("right:50%;width:{:.1f}%".format(bw) if dev < 0
                    else "left:50%;width:{:.1f}%".format(bw))
        spark = sparkline(series[h], cidx[h], sp_lo, sp_hi,
                          width=2.4 if ishome else 1.6)
        prow.append(
            '<div class="prow{me}"><span class="rk">{i}<em>/{N}</em></span>'
            '<div class="hin"><span class="hname">{nm}{dot}</span>'
            '<span class="hsub">{sub}</span></div>'
            '{spark}'
            '<div class="track"><i class="mid"></i>'
            '<div class="bar {cls}{ov}" style="{bs}"></div></div>'
            '<span class="pv">{mv}</span>'
            '<span class="pi {cls}">{gt}</span>'
            '<span class="mvv">{md} chg · {st} prices</span></div>'.format(
                me=" me" if ishome else "", i=i2, N=N, nm=hlabel(h), dot=dot,
                sub=sub, spark=spark, cls=cls, ov=" over" if over else "",
                bs=barstyle, mv=money(med[h]), gt=gap_txt,
                md=moved_days[h], st=price_steps[h]))

    pospanel = (
        '<div class="panel">\n<h2>Position of each hotel'
        '<span class="h2sub">compared day by day, ranked by average daily rank</span></h2>\n'
        '<div class="phead"><span class="rk">Rank</span>'
        '<span class="hin">Hotel · price range</span>'
        '<span class="sp">Trend</span>'
        '<span class="track">Relative position (centre line = median of the others, full bar = +/-{}%)</span>'
        '<span class="pv">Median price</span>'
        '<span class="pi">vs the others</span>'
        '<span class="mvv">Moves</span></div>\n'
        '<div class="poslist">\n{}</div>\n'
        '<div class="note">'
        '"vs the others" = this hotel’s median price divided by the median price of <b>all the other hotels</b>. '
        'A bar to the left = cheaper, to the right = more expensive; the full bar is fixed at +/-{}%, so today’s board and tomorrow’s can be compared. '
        'All trend lines share one vertical scale. "Moves" = days changed in this run (chg) · different prices used in the window (prices). '
        '<b>More expensive does not mean worse, and cheaper does not mean better.</b></div>\n'
        '</div>\n'
    ).format(BAR_SPAN, "\n".join(prow), BAR_SPAN)

    # ================= panel 5: weekday/weekend + days to stay =================
    def avg_of(vs):
        """Name kept; the rule is the median, the same across the page."""
        return med_of([v for v in vs if v])

    wk_rows, wk_stat = [], {}
    for h in hotels:
        wd2, we2 = [], []
        for d in dates:
            i2 = didx[d]
            v = series[h][i2]
            if not v:
                continue
            (we2 if date(*map(int, d.split("-"))).weekday() in (4, 5)
             else wd2).append(v)
        a, b = avg_of(wd2), avg_of(we2)
        wk_stat[h] = pct(b, a) if (a and b) else None

    # the table only gives "you vs comp set"; your weekend vs your weekday says nothing about position
    wk_vs = {}
    for lab, f in (("Weekdays (Sun-Thu)", lambda d: date(*map(int, d.split("-"))).weekday() not in (4, 5)),
                   ("Weekend (Fri, Sat)", lambda d: date(*map(int, d.split("-"))).weekday() in (4, 5))):
        hv = avg_of([series[home][didx[d]] for d in dates if f(d)]) if home else None
        cv = avg_of([series[c][didx[d]] for c in comps for d in dates if f(d)])
        g2 = pct(hv, cv) if (hv and cv) else None
        wk_vs[lab] = (hv, cv, g2)
        wk_rows.append(
            '<tr><th>{}</th><td>{}</td><td>{}</td><td class="{}">{}</td></tr>'.format(
                lab, money(hv) if hv else "—", money(cv) if cv else "—",
                "pos" if (g2 or 0) > 0.5 else ("neg" if (g2 or 0) < -0.5 else "flat"),
                ("—" if g2 is None else "{:.0f}% above".format(g2) if g2 > 0.5 else
                 ("{:.0f}% below".format(-g2) if g2 < -0.5 else "About the same"))))

    bands = [("Next 7 days", 0, 6), ("Days 8 to 14", 7, 13), ("After 14 days", 14, 99)]
    bd_rows, band_stat = [], {}
    for nm, a, b in bands:
        idxs = [i2 for i2 in range(len(dates)) if a <= i2 <= b]
        if not idxs:
            continue
        hv = avg_of([series[home][i2] for i2 in idxs]) if home else None
        cv = avg_of([series[c][i2] for c in comps for i2 in idxs])
        gg = pct(hv, cv) if (hv and cv) else None
        band_stat[nm] = (hv, cv, gg)
        bd_rows.append(
            '<tr><th>{}</th><td>{}</td><td>{}</td><td class="{}">{}</td></tr>'.format(
                nm, money(hv) if hv else "—", money(cv) if cv else "—",
                "pos" if (gg or 0) > 0.5 else ("neg" if (gg or 0) < -0.5 else "flat"),
                ("{:.0f}% above".format(gg) if gg and gg > 0.5 else
                 ("{:.0f}% below".format(-gg) if gg and gg < -0.5 else
                  ("About the same" if gg is not None else "—")))))

    structpanel = (
        '<div class="panel"><h2>Price structure'
        '<span class="h2sub">the same data from two angles</span></h2>'
        '<div class="two">'
        '<div class="half"><h3>Weekday vs weekend</h3>'
        '<table class="mini"><thead><tr><th></th><th>You</th>'
        '<th>Comp set</th><th>You vs comp set</th></tr></thead><tbody>{}</tbody></table>'
        '<div class="note">This compares you with the comp set within the same period, not your weekend with your own weekday.</div></div>'
        '<div class="half"><h3>Days until stay</h3>'
        '<table class="mini"><thead><tr><th></th><th>You</th>'
        '<th>Comp set</th><th>You vs comp set</th></tr></thead>'
        '<tbody>{}</tbody></table>'
        '<div class="note">Prices only. <b>Do not compare sold-out rates across stay dates</b>: the closer a date is to today, the longer it has been on sale, so it sells out more easily, which says nothing about demand.</div></div>'
        '</div></div>\n').format("".join(wk_rows), "".join(bd_rows))

    # ================= line chart =================
    vmin, vmax = (min(allnorm), max(allnorm)) if allnorm else (0, 500)
    step = 100
    for cand in (100, 200, 250, 500, 1000, 2000, 5000):
        step = cand
        if (vmax * 1.04 - vmin) / cand <= 6:
            break
    lo = int(vmin // step * step)
    hi = int(-(-int(vmax * 1.04) // step) * step)
    if hi <= lo:
        hi = lo + step
    chart = {
        "hotels": hotels,
        "names": [short(h) for h in hotels],
        "home": short(home) if home else "",
        "dates": dates,
        "series": series,
        "raw": raw,
        "suite": {h: suite[h] for h in hotels},
        "colors": [cidx[h] for h in hotels],
        "events": {str(didx[k]): "; ".join(v) for k, v in events.items() if k in didx},
        "weeks": [WEEK[date(*map(int, d.split("-"))).weekday()] for d in dates],
        "lo": lo,
        "hi": hi,
        "step": step,
    }

    comp_h = "Comp-set median" if home else "Median"

    # ================= calendar =================
    # Each cell shows only your price and how far above or below the comp-set median it is.
    # Position is shown by the cell colour: zero is the axis, warm = more expensive, cool = cheaper,
    # stronger = bigger gap. Other detail goes in the hover text, not in the cell.
    # Red means you are more expensive than the comp set; it does not mean bad.
    def cal_tone(g, sold):
        # 5 tiers, zero is the axis, there is no "equal" tier
        if sold:
            return "cs"
        if g is None:
            return "cna"
        if g >= 20:
            return "w3"
        if g >= 10:
            return "w2"
        if g >= 0:
            return "w1"
        if g > -10:
            return "k1"
        return "k2"

    d_first = date(*map(int, dates[0].split("-")))
    d_last = date(*map(int, dates[-1].split("-")))
    mons, yy, mm = [], d_first.year, d_first.month
    while (yy, mm) <= (d_last.year, d_last.month):
        mons.append((yy, mm))
        mm += 1
        if mm > 12:
            mm, yy = 1, yy + 1

    cal_mon = []
    for yy, mm in mons:
        f1 = date(yy, mm, 1)
        ndays = (date(yy + (mm == 12), (mm % 12) + 1, 1) - f1).days
        cs = ['<div class="cpad"></div>'] * f1.weekday()
        for dd in range(1, ndays + 1):
            key = "{:04d}-{:02d}-{:02d}".format(yy, mm, dd)
            if key not in didx:
                cs.append('<div class="cc cna coff"><span class="cd">{}</span></div>'.format(dd))
                continue
            i4 = didx[key]
            hv = series[home][i4] if home else None
            cv = comp_med.get(key) if home else day_med.get(key)
            sold = (data.get((home, key)) or {}).get("status") == "soldout" if home else False
            g4 = pct(hv, cv) if (hv and cv) else None
            tip = "; ".join(
                "{} {}".format(short(h),
                               money(series[h][i4]) if series[h][i4]
                               else ("Sold out" if (data.get((h, key)) or {}).get("status") == "soldout"
                                     else "No price"))
                for h in hotels)
            if cv:
                tip += " | {} {}".format(comp_h, money(cv))
            if home and key in occ:
                tip += " | Your occupancy {:.0f}%".format(occ[key])
            if key in events:
                tip += " | Event: " + ", ".join(events[key])
            if sold:
                pv4 = (data.get((home, key)) or {}).get("prev") or ""
                big = '<span class="cb so">Sold out</span>'
                sub = ('<span class="cv">Sold at {} last run</span>'.format(money(int(pv4)))
                       if pv4 and not was_suite(home, int(pv4)) else '<span class="cv">—</span>')
            else:
                big = '<span class="cb">{}</span>'.format(money(hv) if hv else "—")
                sub = ('<span class="cv">{}{:.0f}% vs comp set</span>'.format(
                    "+" if g4 > 0 else ("−" if g4 < 0 else ""), abs(g4)) if g4 is not None
                    else '<span class="cv">—</span>')
            evdot = '<span class="evdot" title="Event"></span>' if key in events else ""
            cs.append('<div class="cc {}" title="{}"><span class="cd">{}{}</span>{}{}</div>'.format(
                cal_tone(g4, sold), tip.replace('"', "&quot;"), dd, evdot, big, sub))
        cal_mon.append(
            '<div class="cmon"><h3>{} {}</h3><div class="cgrid">{}{}</div></div>'.format(
                MON[mm - 1], yy,
                "".join('<div class="cwh">{}</div>'.format(x) for x in WEEK), "".join(cs)))

    calpanel = (
        '<div class="panel"><h2>Calendar'
        '<span class="h2sub">large figure = your price that day, line below = how far above or below the {}; the cell colour follows that percentage</span></h2>'
        '<div class="ckey">'
        '<span><i class="w3"></i>Above by more than 20%</span><span><i class="w2"></i>Above by 10-20%</span>'
        '<span><i class="w1"></i>Above by 0-10%</span>'
        '<span><i class="k1"></i>Below by 0-10%</span><span><i class="k2"></i>Below by more than 10%</span>'
        '<span><i class="cs"></i>You are sold out</span>'
        '</div>{}'
        '<div class="note">Hover over a cell to see every hotel’s price that day. '
        '<b>Red only means you are above the comp set; it does not mean bad.</b></div></div>\n').format(
        comp_h.lower(), "".join(cal_mon))

    # ================= daily price table =================
    thead = "".join(
        '<th class="{}">{}</th>'.format(
            "homecol" if h == home else "",
            "You" if h == home else short(h))
        for h in hotels)
    thead += '<th class="davg-h">{}</th>'.format(comp_h)
    if home:
        thead += '<th class="davg-h">You vs comp set</th>'
    if occ and home:
        thead += '<th class="davg-h">Your occupancy</th>'
    if events:
        thead += '<th class="evh">Events</th>'

    body = []
    for d in dates:
        i2 = didx[d]
        y, m, dd = d.split("-")
        w = WEEK[date(int(y), int(m), int(dd)).weekday()]
        cells = []
        for h in hotels:
            r = data.get((h, d))
            hc = " homecol" if h == home else ""
            if not r or not r["curr"]:
                sold = bool(r and r.get("status") == "soldout")
                tag = "Sold out" if sold else "No price"
                pv = (r or {}).get("prev") or ""
                sub = ('<span class="was">previous run {}</span>'.format(money(int(pv)))
                       if pv else "")
                cells.append('<td class="miss {}{}">{}{}</td>'.format(
                    "soldout" if sold else "noprice", hc, tag, sub))
                continue
            cur = int(r["curr"])
            # Prices are always black; days with only a high-price room left get a grey dotted underline,
            # because they are excluded from medians and the chart and would otherwise be invisible.
            numcls = "num out" if suite[h][i2] else "num"
            diff = r.get("diff", "")
            pv_raw = r.get("prev") or ""
            if suite[h][i2] or (pv_raw and was_suite(h, int(pv_raw))):
                diff = ""     # if either end is a high-price room type the gap is room type, not price: no small print
            if diff not in ("", None) and int(diff) != 0:
                dv = int(diff)
                dhtml = '<span class="d {}">{}{}</span>'.format(
                    "up" if dv > 0 else "down", "+" if dv > 0 else "-", money(abs(dv)))
            else:
                dhtml = ""
            ttl = (' title="Only a suite or other high-price room type was left that day; excluded from the median and the chart"'
                   if suite[h][i2] else '')
            cells.append('<td class="p{}"><span class="{}"{}>{}</span>{}</td>'.format(
                hc, numcls, ttl, money(cur), dhtml))

        ca = comp_med.get(d) if home else day_med.get(d)
        cn = comp_n.get(d, 0) if home else day_n.get(d, 0)
        full = len(comps) if home else len(hotels)
        if ca:
            mark = ('<i class="cn">{} hotels</i>'.format(cn)) if cn < full else ""
            avgcell = '<td class="davg">{}{}</td>'.format(money(ca), mark)
        else:
            avgcell = '<td class="davg thin">—</td>'
        rowcells = "".join(cells) + avgcell
        if home:
            hv = series[home][i2]
            g = pct(hv, ca) if (hv and ca) else None
            if g is None:
                rowcells += '<td class="hgap thin">—</td>'
            else:
                rowcells += '<td class="hgap {}">{}{:.0f}%</td>'.format(
                    "pos" if g > 0.5 else ("neg" if g < -0.5 else "flat"),
                    "+" if g > 0.5 else ("-" if g < -0.5 else ""), abs(g))
        if occ and home:
            rowcells += ('<td class="davg">{:.0f}%</td>'.format(occ[d]) if d in occ
                         else '<td class="davg thin">—</td>')
        if events:
            rowcells += '<td class="evc">{}</td>'.format(
                "; ".join(events[d]) if d in events else "")
        tight = soldout_n.get(d, 0) >= 2
        badge = '<em>{}</em>'.format(w)
        if tight:
            badge += '<em class="tight">{} sold out</em>'.format(soldout_n[d])
        body.append('<tr{}><th class="dt">{} {} {}</th>{}</tr>'.format(
            ' class="tightrow"' if tight else "", MON[int(m) - 1], int(dd), badge, rowcells))

    # ================= CSS =================
    css = """
:root{
 --ink:#1f2328; --mute:#6b7280; --faint:#9aa0a6; --line:#e8eaed; --hair:#f1f3f5;
 --up:#2e7d51; --down:#c4544c; --home:#2f6fed; --homebg:#f5f9ff; --suite:#c77a1e;
 --f1:20px; --f2:15px; --f3:13.5px; --f4:12.5px; --f5:11px;
}
*{box-sizing:border-box}
body{margin:0;padding:24px 28px 44px;background:#f6f7f9;color:var(--ink);
font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
font-size:var(--f4);line-height:1.5;-webkit-font-smoothing:antialiased}
h1{font-size:var(--f1);margin:0 0 5px;font-weight:600;letter-spacing:-.2px}
h2{font-size:var(--f2);margin:0 0 12px;font-weight:600}
h3{font-size:var(--f4);margin:0 0 8px;font-weight:600;color:var(--ink)}
.meta{color:var(--mute);font-size:var(--f4);margin-bottom:18px}
.meta b{color:var(--ink);font-weight:600}
.panel{background:#fff;border:1px solid var(--line);border-radius:10px;
padding:16px 18px 13px;margin-bottom:16px}
.panel.lead{border-color:#cfe0fd;box-shadow:0 1px 0 #e8f0fe}
.panel.lead h2{color:var(--home)}
.h2sub{font-size:var(--f5);font-weight:400;color:var(--faint);margin-left:10px}
.note{color:var(--faint);font-size:var(--f5);margin-top:10px;line-height:1.75}
.note b{color:var(--mute);font-weight:600}
.empty{color:var(--faint);font-size:var(--f4);padding:4px 0 8px}
.meh{font-style:normal;color:var(--home);font-weight:600}
/* your four tiles */
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:2px 0}
.tile{background:#fbfcfd;border:1px solid var(--hair);border-radius:8px;padding:12px 14px}
.tb{font-size:var(--f1);font-weight:600;line-height:1.3;font-variant-numeric:tabular-nums}
.tb.up{color:var(--suite)}.tb.down{color:var(--up)}
.tl{font-size:var(--f5);color:var(--faint);margin-top:2px}
/* small tables */
table.mini{border-collapse:separate;border-spacing:0;width:100%}
table.mini th,table.mini td{padding:7px 10px;font-size:var(--f4);text-align:right;
vertical-align:middle;border-bottom:1px solid var(--hair);white-space:nowrap;
font-variant-numeric:tabular-nums}
table.mini thead th{color:var(--faint);font-weight:400;font-size:var(--f5);
border-bottom:1px solid var(--line)}
table.mini thead th:first-child{text-align:left}
table.mini tbody th{text-align:left;font-weight:600;color:var(--ink)}
table.mini tr:last-child th,table.mini tr:last-child td{border-bottom:none}
table.mini tr.me th,table.mini tr.me td{background:var(--homebg)}
table.mini td.pos{color:var(--suite)}
table.mini td.neg{color:var(--up)}
table.mini td.flat{color:var(--faint)}
table.wide td.c{color:var(--mute)}
table.wide td.ev{color:var(--mute);font-variant-numeric:normal}
table.wide b{font-weight:600}
table.wide b.up{color:var(--up)}
table.wide b.down{color:var(--down)}
.when{color:var(--faint);font-size:var(--f5);margin-left:6px}
/* dates to watch */
.cl{list-style:none;margin:0;padding:0}
.cl li{padding:9px 0;border-bottom:1px solid var(--hair)}
.cl li:last-child{border-bottom:none}
.cl li>b{display:block;font-size:var(--f3);font-weight:600;margin-bottom:2px}
.cl span b{display:inline;font-size:inherit;color:var(--ink);font-weight:600}
.cl span{color:var(--mute);font-size:var(--f4);font-variant-numeric:tabular-nums}
.wl{list-style:none;margin:0;padding:0}
.wl li{display:flex;align-items:center;gap:10px;padding:7px 0;
border-bottom:1px solid var(--hair);font-size:var(--f4)}
.wl li:last-child{border-bottom:none}
.wd{width:94px;flex:none;font-weight:600}
.wt{flex:none;width:76px;text-align:center;font-size:var(--f5);border-radius:4px;
padding:2px 0;font-weight:600}
.wt.comp_down{color:var(--up);background:#eaf5ef}
.wt.comp_up{color:var(--suite);background:#fdf3e6}
.wt.home_sold{color:var(--down);background:#fcecea}
.wt.home_high{color:var(--home);background:#eef4fe}
.wx{color:var(--mute);font-variant-numeric:tabular-nums}
/* position panel */
.poslist{display:flex;flex-direction:column}
.phead{display:flex;align-items:flex-end;gap:14px;padding:0 0 7px;
border-bottom:1px solid var(--line);font-size:var(--f5);color:var(--faint)}
.phead .rk{width:40px;text-align:center}
.phead .hin{width:180px}
.phead .sp{text-align:center}
.phead .track{background:none;height:auto}
.phead .pv{width:78px;text-align:right}
.phead .pi{width:74px;text-align:right}
.phead .mvv{width:118px;text-align:right}
.prow{display:flex;align-items:center;gap:14px;padding:9px 0;
border-bottom:1px solid var(--hair)}
.prow:last-child{border-bottom:none}
.prow.me{background:var(--homebg);margin:0 -10px;padding-left:10px;padding-right:10px;
border-radius:6px}
.rk{width:40px;flex:none;font-size:var(--f3);font-weight:600;text-align:center;
font-variant-numeric:tabular-nums}
.rk em{font-style:normal;font-size:var(--f5);color:var(--faint);font-weight:400}
.hin{width:180px;flex:none;display:flex;flex-direction:column;line-height:1.35;
white-space:nowrap}
.hname{font-size:var(--f3);font-weight:600}
.hsub{font-size:var(--f5);color:var(--faint)}
.hdot{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--suite);margin-left:6px;vertical-align:2px}
.sp{width:70px;height:22px;flex:none;display:block}
.track{flex:1;position:relative;height:14px;border-radius:3px;min-width:120px;
background:linear-gradient(to right,#f1f7f4 0 50%,#fdf6ec 50% 100%)}
.bar{position:absolute;top:0;height:14px;border-radius:3px;background:#4e9d74}
.bar.pos{background:#d8933e}
.bar.flat{background:#aab2bb}
.bar.over::after{content:"";position:absolute;top:50%;width:0;height:0;
border-top:4px solid transparent;border-bottom:4px solid transparent}
.bar.pos.over::after{right:-5px;transform:translateY(-50%);border-left:5px solid #d8933e}
.bar.neg.over::after{left:-5px;transform:translateY(-50%);border-right:5px solid #4e9d74}
.mid{position:absolute;left:50%;top:-4px;height:22px;width:0;
border-left:1px solid #aab2bb;transform:translateX(-.5px)}
.pv{width:78px;flex:none;text-align:right;font-size:var(--f3);font-weight:600;
font-variant-numeric:tabular-nums}
.pi{width:74px;flex:none;text-align:right;font-size:var(--f3);font-weight:600;
font-variant-numeric:tabular-nums}
.pi.neg{color:var(--up)} .pi.pos{color:var(--suite)} .pi.flat{color:var(--faint)}
.mvv{width:118px;flex:none;text-align:right;font-size:var(--f5);color:var(--faint);
white-space:nowrap;font-variant-numeric:tabular-nums}
/* structure columns */
.two{display:grid;grid-template-columns:1fr 1fr;gap:22px}
/* line chart */
.lgb{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:8px}
.lgb span{display:inline-flex;align-items:center;gap:6px;font-size:var(--f4);
color:var(--mute);cursor:pointer;user-select:none}
.lgb span.off{opacity:.3}
.lgb i{width:16px;height:3px;border-radius:2px;display:inline-block}
.chartbox{position:relative}
svg#chart{display:block;width:100%;height:auto;overflow:visible}
.tip{position:absolute;pointer-events:none;background:rgba(255,255,255,.98);
border:1px solid #d9dde2;border-radius:8px;box-shadow:0 4px 18px rgba(20,30,50,.12);
padding:9px 11px;font-size:var(--f4);min-width:180px;display:none;z-index:9}
.tip .td{font-weight:600;margin-bottom:6px}
.tip .tr{display:flex;justify-content:space-between;gap:14px;padding:1.5px 0;color:var(--mute)}
.tip .tr b{color:var(--ink);font-variant-numeric:tabular-nums}
.tip .tr i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
/* calendar */
.cmon{margin-top:10px}
.cmon h3{font-size:var(--f4);margin:0 0 8px}
.cgrid{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}
.cwh{font-size:var(--f5);color:var(--faint);text-align:center;padding-bottom:2px}
.cpad{min-height:72px}
.cc{min-height:72px;border-radius:7px;padding:6px 9px;display:flex;flex-direction:column}
.cd{font-size:var(--f5);color:#8a9099}
.evdot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#7b5ea7;margin-left:5px;vertical-align:1px}
table.day th.evh,table.day td.evc{text-align:left;white-space:normal;min-width:150px;color:#5b4a7a}
.cb{font-size:17px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.3;margin-top:1px}
.cb.so{font-size:var(--f3);color:#b3453c}
.cv{font-size:var(--f5);margin-top:auto;font-variant-numeric:tabular-nums}
.w3{background:#f6cdc6}.w3 .cv{color:#9d352b}
.w2{background:#fbdcc9}.w2 .cv{color:#9c5420}
.w1{background:#fdf4e4}.w1 .cv{color:#8d7033}
.k1{background:#e1f0e5}.k1 .cv{color:#35724c}
.k2{background:#c9e4d3}.k2 .cv{color:#1f5c39}
.cs{background:#f3e3e1}.cs .cv{color:#9a6b66}
.cna{background:#fafbfc}.cna .cv{color:#b8bcc1}
.coff{opacity:.4}
.ckey{display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:var(--f5);
color:var(--faint);margin-bottom:2px}
.ckey span{display:inline-flex;align-items:center;gap:5px}
.ckey i{width:20px;height:11px;border-radius:3px;display:inline-block}
/* daily price table */
/* .tablewrap is retired: it breaks sticky headers */
table.day{border-collapse:separate;border-spacing:0;width:100%;background:#fff;
border-radius:10px}
.bare table.day{border:1px solid var(--line)}
table.day th,table.day td{padding:7px 13px;text-align:right;vertical-align:middle;
border-bottom:1px solid var(--hair);white-space:nowrap;font-variant-numeric:tabular-nums}
table.day thead th{position:sticky;top:0;z-index:3;background:#fff;
font-size:var(--f5);font-weight:600;color:var(--mute);text-align:right;
padding-top:11px;padding-bottom:9px;border-bottom:1px solid var(--line);
box-shadow:0 1px 0 var(--line)}
table.day thead th.homecol{color:var(--home)}
table.day thead th:first-child{left:0;z-index:5;text-align:left}
table.day tbody th.dt{text-align:left;font-weight:600;font-size:var(--f4);
background:#fff;position:sticky;left:0;z-index:2}
table.day tbody th.dt em{font-style:normal;color:var(--faint);font-weight:400;
font-size:var(--f5);margin-left:5px}
table.day tbody th.dt em.tight{color:var(--suite);font-weight:600}
tr.tightrow th.dt,tr.tightrow td{background:#fffdfa}
td.p{font-size:var(--f3);font-weight:600}
td.homecol,th.homecol{background:var(--homebg)}
tr.tightrow td.homecol{background:#f6f9fe}
td.miss{color:var(--faint);font-weight:400;font-size:var(--f4);text-align:center}
td.soldout{background:#fdeeed;color:var(--down);font-weight:600}
td.noprice{background:#f3f4f6;color:var(--faint)}
tr.tightrow td.soldout{background:#fdeae8}
td.miss .was{display:block;font-size:var(--f5);color:var(--faint);margin-top:1px;
font-weight:400}
td.davg{color:var(--mute);font-size:var(--f4);border-left:1px solid var(--line)}
td.davg .cn{font-style:normal;font-size:var(--f5);color:var(--faint);margin-left:4px}
td.davg.thin{color:#c3c7cc}
td.hgap{font-size:var(--f4);font-weight:600}
td.hgap.pos{color:var(--suite)}td.hgap.neg{color:var(--up)}td.hgap.flat{color:var(--faint)}
td.hgap.thin{color:#c3c7cc;font-weight:400}
th.davg-h{border-left:1px solid var(--line)}
.num{display:block;line-height:1.35}
.out{border-bottom:1px dotted #c3c7cc;padding-bottom:1px}
.d{display:block;font-size:var(--f5);font-weight:400;line-height:1.3}
.d.up{color:var(--up)} .d.down{color:var(--down)}
/* footer notes */
.foot{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px}
.fbox{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 15px}
.fbox ul{margin:0;padding-left:16px}
.fbox li{color:var(--faint);font-size:var(--f5);line-height:1.75;margin-bottom:5px}
.fbox li:last-child{margin-bottom:0}
.fbox b{color:var(--mute)}
.fbox i.sw{display:inline-block;width:9px;height:9px;border-radius:2px;
margin-right:5px;vertical-align:-1px}
@media(max-width:1100px){.tiles{grid-template-columns:repeat(2,1fr)}
.two{grid-template-columns:1fr}.foot{grid-template-columns:1fr}.sp{display:none}}
@media print{
 body{background:#fff;padding:0 0 10px}
 .panel,.fbox{border-color:#d9dde2}
 table.day thead th{position:static;box-shadow:none}
 table.day tbody th.dt{position:static}
 table.day thead{display:table-header-group}
 table.day tbody tr{break-inside:avoid}
 .tiles,.tile,.fbox,.prow,.half,h2,.cmon{break-inside:avoid}
 h2,h3{break-after:avoid}
 .chartbox{break-inside:avoid}
 .noprint{display:none}
 *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""

    # ================= assemble =================
    html = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>Competitor rate board</title>\n<style>' + css + '</style></head><body>\n')

    html += '<h1>Competitor rate board</h1>\n'
    prevtxt = ""
    if prev_stamp:
        g = gap_text(stamp, prev_stamp)
        prevtxt = " · compared with previous run <b>{}</b>{}".format(
            pretty_stamp(prev_stamp), " ({})".format(g) if g else "")
    html += ('<div class="meta">Collected <b>{}</b>{} · covers <b>{} ~ {}</b>'
             ' ({} stay date{}, 1 night, 1 room){} · <b>{} price{}</b> · <b>{} sold out</b>'
             '</div>\n').format(
        stamp, prevtxt, d0, d1, len(dates), "" if len(dates) == 1 else "s",
        " · prices in <b>{}</b>".format(currency) if currency else "", ok, "" if ok == 1 else "s", soldout_total)

    if coverage_warn:
        html += '<div class="panel" style="border-left:4px solid #c77a1e"><b>Check this run.</b> ' + coverage_warn + '</div>\n'
    html += homepanel
    html += changepanel
    html += pospanel
    html += structpanel

    html += ('<div class="panel">\n<h2>Lowest price trend</h2>\n'
             '<div class="lgb" id="lgb"></div>\n'
             '<div class="chartbox"><svg id="chart" viewBox="0 0 1120 400"></svg>\n'
             '<div class="tip" id="tip"></div></div>\n'
             '<div class="note noprint">Hover over any day to list every hotel’s price. '
             'Click a name in the legend to hide that hotel. {}{}</div>\n</div>\n').format(
        "Your line is drawn thicker." if home else "",
        " A purple marker at the top = a city event that day." if events else "")

    html += calpanel

    # Never wrap the table in an overflow container: sticky headers then only stick inside it.
    # Let the whole page scroll sideways instead; header row and date column stay pinned.
    table_html = ('<table class="day">\n<thead><tr><th>Stay date</th>{}</tr></thead>\n'
                  '<tbody>{}</tbody>\n</table>').format(thead, "".join(body))
    html += '<div class="bare">{}</div>\n'.format(table_html)

    namelist = "; ".join(
        "{} = {}".format("You" if h == home else short(h), h) for h in hotels)
    html += ('<div class="foot">'
             '<div class="fbox"><h3>Definitions</h3><ul>'
             '<li>The whole page uses the <b>median</b>, not the mean (a mean is pulled by one extreme price)</li>'
             '<li>"{}" = the middle value of the hotels with a normal price that day; the count is shown when it is short, and "—" appears when fewer than 2 hotels have a price</li>'
             '<li>The number of hotels that can be compared changes every day, so this column read down the page is not a trend</li>'
             '<li>Every percentage is one number on the page divided by another, so you can check it</li>'
             '<li>Lowest bookable price under the same search conditions every run (1 room, 1 night, 1 adult); dates roll forward</li>'
             '</ul></div>'
             '<div class="fbox"><h3>Price cells</h3><ul>'
             '<li>Normal prices have no background; the small figure below = change from the previous run, '
             '<b style="color:#2e7d51">+</b> higher, <b style="color:#c4544c">−</b> lower, blank if unchanged</li>'
             '<li>A figure with a <b>grey dotted underline</b> = only a suite or other high-price room type was left (above {} times that hotel’s own median, '
             '{}); excluded from the median and the chart</li>'
             '<li><b style="color:#c4544c">Sold out</b> = no rooms left, with the previous run’s price below; '
             '<b>No price</b> = nothing was read. Neither is ever filled in</li>'
             '<li>A <b style="color:#c77a1e">"N sold out"</b> tag next to a date = two or more hotels sold out that day</li>'
             '</ul></div>'
             '<div class="fbox"><h3>Hotels</h3><ul>'
             '<li>{}</li>'
             '<li>Add or remove a hotel and every percentage is recalculated</li>'
             '</ul></div>'
             '</div>\n').format(comp_h, SUITE_RATIO,
        "or above {}".format(CAP) if CAP is not None else "applied once there are at least {} normal days".format(MIN_DAYS), namelist)

    html += '<script>\nconst D = ' + json.dumps(chart, ensure_ascii=False) + ';\n</script>\n'
    html += CHART_JS
    html += "</body></html>"
    html = html.replace("__CNT__", str(len(hotels)))
    open(OUT, "w", encoding="utf-8").write(html)
    print("BOARD", OUT)
    print("HOME", home or "(no home hotel set)")
    print("SUITE_EXCLUDED", suite_n)


CHART_JS = r"""<script>
(function(){
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var W=1120,H=400,padL=52,padR=18,padT=16,padB=42;
var svg=document.getElementById('chart'),tip=document.getElementById('tip');
var H0=D.hotels,NM=D.names,DATES=D.dates,SER=D.series,COL=D.colors,LO=D.lo,HI=D.hi;
var HOME=D.home;
var PW=W-padL-padR,PH=H-padT-padB;
var n=DATES.length,step=n>1?PW/(n-1):PW;
var hidden={};
function X(i){return padL+i*step;}
function Y(v){return padT+PH-((v-LO)/(HI-LO))*PH;}
var NS='http://www.w3.org/2000/svg';
function el(t,a){var e=document.createElementNS(NS,t);for(var k in a)e.setAttribute(k,a[k]);return e;}
var g=el('g',{});svg.appendChild(g);
var stepv=D.step;
for(var v=LO;v<=HI;v+=stepv){
  var y=Y(v);
  g.appendChild(el('line',{x1:padL,y1:y,x2:W-padR,y2:y,stroke:v===LO?'#c9ced4':'#eef0f3','stroke-width':1}));
  var t=el('text',{x:padL-9,y:y+4,'text-anchor':'end','font-size':11,fill:'#9aa0a6'});
  t.textContent=v.toLocaleString();g.appendChild(t);
}
DATES.forEach(function(d,i){
  var x=X(i),m=+d.split('-')[1],dd=+d.split('-')[2];
  var we=(D.weeks[i]==='Fri'||D.weeks[i]==='Sat');
  if(we){g.appendChild(el('rect',{x:x-step/2,y:padT,width:step,height:PH,fill:'#fafbfd'}));}
  g.appendChild(el('line',{x1:x,y1:padT+PH,x2:x,y2:padT+PH+4,stroke:'#d6dae0'}));
  if(i%2===0||i===n-1){
    var t=el('text',{x:x,y:padT+PH+19,'text-anchor':'middle','font-size':10.5,fill:'#7a7f85'});
    t.textContent=m+'/'+dd;g.appendChild(t);
    var w=el('text',{x:x,y:padT+PH+32,'text-anchor':'middle','font-size':9.5,
      fill:we?'#b06000':'#b0b4b9'});
    w.textContent=D.weeks[i];g.appendChild(w);
  }
});
Object.keys(D.events||{}).forEach(function(k){
  var x=X(+k);
  var tri=el('path',{d:'M'+(x-5)+','+padT+' L'+(x+5)+','+padT+' L'+x+','+(padT+8)+' Z',fill:'#7b5ea7'});
  var tt=el('title',{});tt.textContent=D.events[k];tri.appendChild(tt);g.appendChild(tri);
});
var lines=[];
H0.forEach(function(h,hi){
  var arr=SER[h],path='',pen=false,isHome=(NM[hi]===HOME&&HOME);
  arr.forEach(function(v,i){
    if(v===null){pen=false;return;}
    var x=X(i),y=Y(v);
    path+=(pen?'L':'M')+x.toFixed(1)+','+y.toFixed(1)+' ';pen=true;
  });
  var gg=el('g',{});
  gg.appendChild(el('path',{d:path,fill:'none',stroke:COL[hi],
    'stroke-width':isHome?3:1.8,'stroke-linejoin':'round','stroke-linecap':'round',
    opacity:isHome?1:.72}));
  arr.forEach(function(v,i){
    if(v===null){
      gg.appendChild(el('circle',{cx:X(i),cy:padT+PH-5,r:2.6,fill:'none',
        stroke:'#c4c9cf','stroke-width':1.4}));
      return;
    }
    gg.appendChild(el('circle',{cx:X(i),cy:Y(v),r:isHome?3.4:2.6,fill:'#fff',
      stroke:COL[hi],'stroke-width':isHome?2.2:1.6,opacity:isHome?1:.85}));
  });
  g.appendChild(gg);lines.push(gg);
});
var vline=el('line',{x1:0,y1:padT,x2:0,y2:padT+PH,stroke:'#9aa0a6','stroke-width':1,
  'stroke-dasharray':'3 3',opacity:0});g.appendChild(vline);
svg.addEventListener('mousemove',function(ev){
  var box=svg.getBoundingClientRect();
  var px=(ev.clientX-box.left)/box.width*W;
  var i=Math.round((px-padL)/step);
  if(i<0||i>=n){tip.style.display='none';vline.setAttribute('opacity',0);return;}
  var x=X(i);
  vline.setAttribute('x1',x);vline.setAttribute('x2',x);vline.setAttribute('opacity',1);
  var d=DATES[i],m=+d.split('-')[1],dd=+d.split('-')[2];
  var html='<div class="td">'+D.weeks[i]+' '+MON[m-1]+' '+dd+'</div>';
  H0.forEach(function(h,hi){
    if(hidden[h])return;
    var v=SER[h][i],rv=D.raw[h][i],su=D.suite[h][i];
    var val;
    if(v!==null){val='<b>'+v.toLocaleString()+'</b>';}
    else if(su&&rv){val='<b style="color:#b06000">'+rv.toLocaleString()+'</b>'+
      '<span style="color:#b06000;font-size:11px"> high-price room</span>';}
    else{val='<b style="color:#b0b4b9">sold out</b>';}
    var nm=(NM[hi]===HOME&&HOME)?'You':NM[hi];
    html+='<div class="tr"><span><i style="background:'+COL[hi]+'"></i>'+nm+'</span>'+val+'</div>';
  });
  if(D.events&&D.events[i]){html+='<div class="tr"><span style="color:#7b5ea7">Event</span><b>'+D.events[i]+'</b></div>';}
  tip.innerHTML=html;tip.style.display='block';
  var left=(x/W)*box.width+12, tw=tip.offsetWidth, bw=box.width;
  if(left+tw>bw-4)left=(x/W)*box.width-tw-12;
  tip.style.left=Math.max(0,left)+'px';
  var ty=(ev.clientY-box.top)-10;tip.style.top=Math.max(0,ty)+'px';
});
svg.addEventListener('mouseleave',function(){tip.style.display='none';vline.setAttribute('opacity',0);});
var lg=document.getElementById('lgb');
H0.forEach(function(h,hi){
  var s=document.createElement('span');
  s.innerHTML='<i style="background:'+COL[hi]+'"></i>'+
    ((NM[hi]===HOME&&HOME)?'<b style="color:#2f6fed">You</b>':NM[hi]);
  s.onclick=function(){
    hidden[h]=!hidden[h];
    s.className=hidden[h]?'off':'';
    lines[hi].style.display=hidden[h]?'none':'';
  };
  lg.appendChild(s);
});
})();
</script>
"""


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.getcwd(), help="project folder")
    ap.add_argument("--home", default=None, help="your hotel (name or short name; set once)")
    ap.add_argument("--cap", type=float, default=None,
                    help="optional: treat any price above this number as a high-price room type (depends on your currency)")
    a = ap.parse_args()
    if a.cap:
        CAP = a.cap
    set_data_dir(a.data_dir)
    main(a.home)
