# Ctrip guide

This tool is built around **Ctrip (the mainland China site)**. The board itself reads one simple table, so prices from
other sources can be imported as a CSV, but only the Ctrip collector in this repository has been tested by the author.
Nothing else is claimed.

---

## 1. Trip.com is not Ctrip

If you run a hotel **outside China** and a large share of your guests are **from mainland China**,
those guests mostly search and book on **Ctrip (the Chinese-language site and app)**, not on Trip.com.

A competitor rate check that only covers Trip.com can miss the rate your Chinese guests actually see. The two can differ
(they may list different hotels, and Trip.com may show foreign currency while Ctrip shows CNY). These are observations to
verify on your own hotel, not guarantees. Many commercial rate-shopping services find Ctrip hard to cover; Ctrip is known to
limit automated access (the author met a slider verification and a login requirement). Ask your vendor whether the Ctrip
Chinese site is covered.

Keep search conditions identical every run (room count, nights, adults, currency, login state). If you change a condition,
start a new project folder; do not mix it into the old series.

---

## 2. Collecting Ctrip rates: what will happen

This repository includes a Ctrip collector in `connectors/ctrip/` (see its README). Three small scripts:
`ctrip_resolve.py` (hotel names to Ctrip IDs, exact match only), `ctrip_login.py` (you log in by hand, the
session is saved locally) and `ctrip_collect.py` (collects the prices and writes the archive file).
It collects only what the Ctrip list page shows to a logged-in user, slowly, and stops when a verification appears.

These points come from the author's own runs on the Ctrip mainland hotel list page.

1. **You need to be logged in.** Log in yourself in a visible browser window and save the session.
   Never give your password to a script, an AI tool, or this repository.
   **Account notice:** Ctrip limits accounts that make many searches in a short time, so the account
   you log in with may be restricted. Decide beforehand which account you are willing to use.
   Many people use a separate account for monitoring instead of their personal one.
2. **Use the default search once.** 1 room, 1 night, 1 adult. Take the lowest bookable rate shown.
3. **Expect a slider verification.** When it appears, stop the run. Do not try to bypass it,
   do not rotate IPs, do not retry in a loop. Solve it by hand in the visible window, wait,
   then run again with fewer hotels or fewer dates.
4. **Go slowly, and not too often.** The collector pauses a random 0.7 to 1.4 seconds between
   pages. How often it runs is up to your own scheduler, but running it many times a day can get the account
   restricted. Start with once or twice a day and a handful of hotels over 30 days. To refresh only a few
   important dates, use `--dates 2026-12-24,2026-12-31`.
5. **Sessions expire.** If most pages come back empty or send you to the login page, the session is
   stale. Log in again; do not keep retrying.
6. **Record "sold out" and "no price" differently, and never fill gaps.** A sold-out date is a fact.
   A page that opened but showed no price is missing data. Do not copy yesterday's price into either.
7. **Watch for suite-only days.** Some days only a very expensive room is left and the "lowest price"
   jumps to several times the normal level. The board flags a price above 2.5 times that hotel's own
   median as a high-price room type and leaves it out of the medians (this needs at least 10 normal days; you can
   also set an absolute limit with `--cap`).
8. **Check the hotel name matches exactly.** If the search returns several hotels, do not guess. Fix the name.
9. **Terms are your responsibility.** Automated collection may be restricted by the platform.
   Read the current terms and decide for yourself.

---

---

## 3. What goes into the board

One row per hotel, channel and stay date. See `docs/DATA_FORMAT.md`. One channel per board. Other sources can be
imported as a CSV in the same format.

On 2026-11-25 the author tried five other booking channels once, without logging in, and could not read a price on any
of them. That was one attempt on one day from one network, so they are not part of the built-in setup. You can still ask for them in your task.
