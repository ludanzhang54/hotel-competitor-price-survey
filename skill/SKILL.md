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
- Price above 2.5x the hotel's own median, or above 10,000 on a CNY (Ctrip) board (other currencies: optional `--cap`) = high-price room type: shown with a dotted underline, left out of medians and chart. Only compared with that hotel itself, never with other hotels that day.
- Never compare sold-out rates across different stay dates (nearer dates have had longer to sell). Only compare hotels on the same date.
- The board shows data only. Do not add generated conclusions.
- On a verification page: stop. Never bypass, rotate IPs or retry in a loop. Never take or store passwords; the user logs in.
- Hotel names must match exactly; if there are several candidates, list them and ask. Never invent a name or ID.

## Board display rules (do not change them on your own)

- No analysis text, no auto-written conclusions. Notes explain definitions only.
- Calendar: 5 colour tiers only, zero is the axis, no "equal" tier (more expensive 0-10%, 10-20%, 20%+; cheaper 0-10%, 10%+), plus sold out. Never split finer. Red means above the comp set, not bad. The calendar is the only place a normal price gets a background colour; the daily table does not.
- In the daily table prices are always black; a high-price room type gets a grey dotted underline, no change figure, and is left out of the chart and medians. Sold out = light red with last run's price; no price = light grey.
- Position bars use a fixed +/-20% scale; trend sparklines share one vertical axis. Rank is written N/M, never an average like 1.9.
- "Vs the others" is leave-one-out (this hotel's median divided by the median of the other hotels). Equal medians read "About the same", not "—"; "—" only when fewer than 2 hotels have a price; show the count when it is short.
- The daily table header and date column stay pinned; never wrap the table in an overflow container.
- Words: "You" (the hotel name only in the footer) and "competitors" or "comp set"; no currency symbol, "flat", "baseline" or "index" on the page; say what the price is "among the hotels on this list", never the whole city.
- This data has no occupancy or revenue, so never present a price gap as a market-share gap or derive RevPAR.
- Keep to the existing font-size scale. Explain each definition once, in the footer.

## Steps

1. Ask which hotels. The built-in collector is for Ctrip. If the user asks for a different channel or an extra one, do it for them in this task (adapt the collector or build the CSV in the DATA_FORMAT format), keep one channel per board, and check that site's terms first. For Ctrip: read `docs/CHANNELS.md` section 2 and tell the user about the account notice and not running too often.
2. Collect with `connectors/ctrip/` (resolve, login, collect). A CSV from another source in the format of `docs/DATA_FORMAT.md` also works.
3. Build: `python scripts/make_board.py --data-dir <project> --home "<your hotel>"`.
4. Optional: add `occupancy.csv` and `events.csv`; refresh chosen dates with `--dates`; PDF with `scripts/to_pdf.py`.
5. Report what the board shows. If the user wants analysis, do it separately and say so.
