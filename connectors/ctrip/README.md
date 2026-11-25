# Ctrip connector (author-tested)

Collects the lowest bookable price on the **Ctrip mainland hotel list page** for a list of hotels,
for the next N days. Read `docs/CHANNELS.md` section 2 first: it explains the login, the account
notice, the verification page and why this is run slowly.

## Setup (once)

```bash
pip install playwright
playwright install chromium
```

## Steps

Run these from the `connectors/ctrip/` folder. `my_project` below is your own data folder; use any path, ideally outside this repository (it holds your login session and price history).

```bash
# 1. Turn hotel names into the list (exact match only; unmatched names are listed, never guessed)
python ctrip_resolve.py --data-dir my_project --names "Hotel A (Ctrip Chinese name)" "Hotel B"

# 2. Log in yourself in the browser window that opens. Your password is never typed by the script.
python ctrip_login.py --data-dir my_project

# 3. Try 3 dates first
python ctrip_collect.py --data-dir my_project --probe

# 4. Full run, 30 days (or --days 14, or only chosen dates)
python ctrip_collect.py --data-dir my_project
python ctrip_collect.py --data-dir my_project --dates 2026-12-24,2026-12-31

# 5. Build the board (the first run needs --home to say which hotel is yours)
python ../../scripts/make_board.py --data-dir my_project --home "Your Hotel"
```

## What it does and does not do

- Default search only: 1 room, 1 night, 1 adult, lowest bookable price. Prices are CNY, as the Ctrip Chinese site shows them.
- If a verification page appears it **stops the whole run**. It does not bypass it, retry, or change network.
- `sold out` and `no price` are saved as different statuses. Nothing is filled in.
- A hotel counts only when the page shows exactly one result and the name matches.
- If the session looks stale (login page, or 5 empty pages in a row) it stops and tells you to log in again.
- Rows collected before a stop or Ctrl-C are still saved. An incomplete run is flagged on the board.
- The session file `ctrip_state.json` is as sensitive as a password. Never commit or share it
  (it is in `.gitignore`).
- The page text it reads is Chinese; if Ctrip changes its page, the patterns in `EXTRACT_JS` may need updating.
  A pull request that fixes this is welcome.

You are responsible for complying with Ctrip's current terms. Ctrip may restrict an account that makes many
searches in a short time.
