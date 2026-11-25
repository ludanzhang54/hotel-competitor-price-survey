# Data format

The board reads one table. One row is one price observation:
one hotel, on one channel, for one stay date, at one moment.

| Column | Meaning | Example |
|---|---|---|
| `captured_at` | When the price was collected | `2026-11-25 09:30:00` |
| `hotel` | Hotel name, written the same way every run | `Hotel A` |
| `channel` | Where the price was shown | `Ctrip` |
| `stay_date` | Check-in date, one night | `2026-12-01` |
| `price` | The hotel's lowest bookable price that day (any room type, any rate plan). Empty if none | `1280` |
| `currency` | Currency code of the price | `CNY` |
| `status` | `ok`, `soldout`, or `no_price` | `ok` |

## Rules

1. **One channel per board.** Use the same channel, currency, room count, nights and adults for every row.
2. **`soldout` and `no_price` are different.** Sold out is a fact. No price means the page opened but nothing was read.
   Never fill either one with an old price.
3. **Keep every run.** Save each collection as its own file. Never overwrite. The board compares the latest run with the previous one.
4. **One currency per board.** Do not mix currencies in one series.
5. **No analysis columns.** The board shows data only. It does not write conclusions.

Archive files **must be named `run_*.csv`** (the board ignores other names). Prices may contain commas or currency symbols (`1,280`, `¥1280`); they are cleaned. A column named `hotel`, `stay_date` or `price` is required.

## Project folder layout

```
my_project/
  archive/run_2026-11-25_090000.csv   one file per collection run (the table above)
  hotels.csv                          optional: hotel,short_name  (also acts as the watch list)
  home.txt                            written by the board once you pass --home
  ctrip_hotels.csv, ctrip_state.json  only if you use the Ctrip collector (the state file is a login session: never share it)
  occupancy.csv                       optional, see below
  events.csv                          optional, see below
  rate_board.html                     the output
```

## Optional inputs (all optional, use what you have)

If a file is missing, that part of the board is simply left out.

**`occupancy.csv`** — your own hotel's occupancy, shown beside the prices (one column in the daily table, one line in the calendar hover text).

| Column | Example |
|---|---|
| `date` | `2026-12-24` |
| `occupancy` | `83` or `83%` |

**`events.csv`** — city events. Shown as a purple marker on the chart, a dot on the calendar, and an Events column in the daily table.

| Column | Example |
|---|---|
| `date` | `2026-12-31` |
| `event` | `Countdown concert` |
| `end_date` | optional; fills every day from `date` to `end_date` (at most 60 days) |

**Price cap (optional):** `make_board.py --cap 5000` treats any price above that number as a high-price room type. It is off by default because the right number depends on the currency. Without it, only the relative rule applies (above 2.5 times the hotel's own median, once there are 10 normal days).

**`hotels.csv`** — `hotel,short_name`. When present, only these hotels are drawn, and `short_name` is used in tight spaces.
