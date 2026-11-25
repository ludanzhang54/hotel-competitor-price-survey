---
name: hotel-competitor-price-survey
description: Build a competitor rate board for a hotel from prices collected on any channel (one CSV per run). Use when asked for a rate shopping board, competitor price survey, comp-set price comparison, or to collect Ctrip rates for a hotel list.
---

# Hotel Competitor Price Survey

Turns competitor prices into one board: where you stand, what changed since the last run, trend chart, calendar, daily table.
Repository layout: `scripts/make_board.py` (board), `scripts/to_pdf.py`, `connectors/ctrip/` (collector), `docs/`.

## Rules (do not change them on your own)

- The price is each hotel's lowest bookable price (any room type or rate plan); no filters by room type, cancellation or breakfast.
- One channel per board. One currency. Same search conditions every run (1 room, 1 night, 1 adult).
- Keep every run as its own file in `archive/`; never overwrite. The board compares the latest with the previous run.
- Median only, never mean. Every percentage = two numbers shown on the page divided.
- `soldout` and `no_price` are different. Never fill a gap or reuse an old price.
- Price above 2.5x the hotel's own median (optionally also above a `--cap` value you set) = high-price room type: shown with a dotted underline, left out of medians and chart.
- Never compare sold-out rates across different stay dates (nearer dates have had longer to sell). Only compare hotels on the same date.
- The board shows data only. Do not add generated conclusions.
- On a verification page: stop. Never bypass, rotate IPs or retry in a loop. Never take or store passwords; the user logs in.
- Hotel names must match exactly; if there are several candidates, list them and ask. Never invent a name or ID.

## Steps

1. Ask which hotels. The built-in collector is for Ctrip. If the user asks for a different channel or an extra one, do it for them in this task (adapt the collector or build the CSV in the DATA_FORMAT format), keep one channel per board, and check that site's terms first. For Ctrip: read `docs/CHANNELS.md` section 2 and tell the user about the account notice and not running too often.
2. Collect with `connectors/ctrip/` (resolve, login, collect). A CSV from another source in the format of `docs/DATA_FORMAT.md` also works.
3. Build: `python scripts/make_board.py --data-dir <project> --home "<your hotel>"`.
4. Optional: add `occupancy.csv` and `events.csv`; refresh chosen dates with `--dates`; PDF with `scripts/to_pdf.py`.
5. Report what the board shows. If the user wants analysis, do it separately and say so.
