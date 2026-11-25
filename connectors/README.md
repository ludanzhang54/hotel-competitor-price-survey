# Connectors

A connector collects prices from one channel and writes an archive file
(`archive/run_YYYY-MM-DD_HHMMSS.csv`) in the format described in `docs/DATA_FORMAT.md`.
The board does not care how the file was made.

| Connector | Channel | Status |
|---|---|---|
| `ctrip/` | Ctrip (mainland site) | Author-tested |

The built-in connector is Ctrip. Other channels can be added in your own task or by pull request; contributions are welcome (see
`CONTRIBUTING.md`). Only claim what you have tested, and say what you tested it on.
