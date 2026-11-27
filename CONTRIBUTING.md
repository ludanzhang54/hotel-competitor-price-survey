# Contributing

Thank you for helping. This project is maintained by Oriental Horizon Hospitality.

## Ways to help

- **Other connectors**, for example your own booking engine or a paid tool export
- **A fix** when a channel changes its page (for the Ctrip collector, usually the patterns in `EXTRACT_JS` in `connectors/ctrip/ctrip_collect.py`)
- **Board improvements** and **translations**

## How

1. Fork the repository, make a branch, make your change, open a pull request.
2. Say what the change does and, for connectors, **what you tested it on and when**.
3. Keep pull requests small and focused.

## Rules for connectors (in `connectors/<channel>/`)

1. Output the archive format in `docs/DATA_FORMAT.md` and nothing else. One channel per board.
2. **Never fill gaps.** `soldout` and `no_price` are different statuses; do not copy an old price in.
3. **Stop on a verification or CAPTCHA.** Do not add code that bypasses it, rotates IPs, or retries aggressively.
4. **Never ask for or store passwords.** The user logs in themselves; keep session files out of git.
5. **Exact hotel-name matches only.** If there are several candidates, list them and do not guess.
6. Be slow and gentle: random pauses, small volumes.
7. Add a short README in the connector folder: what it collects, what it does not, how to log in, the terms risk.
8. Do not claim a channel works unless you ran it. Update the status in `README.md` and `docs/CHANNELS.md`
   only with what you tested ("Author-tested" is reserved for the maintainer; use "Community-tested" and say by whom and when).
9. Do not add code for sites whose terms forbid automated access without permission.

## Board rules

The board shows data only. Please do not add auto-generated conclusions, mean-based figures, or comparisons of sold-out
rates across different stay dates (a nearer stay date is naturally more likely to be sold out). Every percentage on the
page must be one number on the page divided by another.

## Conduct

Be kind and specific. No scraping of private data, no personal data in issues or pull requests.
