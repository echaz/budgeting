# CSV imports

Bank/card statements are imported from CSV into `Transaction` rows. The
importers live in `scrapers/`. Each imported transaction is locked to an
`ImportFile` record (see `docs/DATA_MODEL.md`).

## Running

Each `Account` has a `statements_dir` (see `docs/DATA_MODEL.md`). The
`import_csv` management command crawls it and imports every `.csv` file with the
chosen parser:

```
docker compose exec web python manage.py import_csv --account "Citi" --source citi
```

- `--account` — the `Account` nickname; its `statements_dir` is crawled.
- `--source` — which parser: `citi`, `santander`, or `chase`.

Each file becomes one `ImportFile`. When an import finishes, that `ImportFile`
is marked `completed=True`; on a later crawl any file whose `(account,
filename)` already has a completed import is **skipped** (identity is by
filename, so a re-downloaded file that keeps its name is treated as already
seen). Row-level dedup below is the second safety net.

## Design goals

- **Idempotent.** Running the same file twice must not create duplicate rows.
- **Duplicate-safe.** Two genuinely identical charges on the same day are both
  real and must both survive.
- **Uncategorized on ingest.** `category` and `domain` are left `NULL`; a later
  human/AI pass fills them in.

## Base class — `scrapers/base.py`

`BaseCsvImporter(account, filename)`:

- `run()` opens the file (`utf-8-sig`, so a leading BOM is stripped), creates the
  `ImportFile` row, iterates rows via `csv.DictReader`, and calls
  `createTransaction(row, import_file)` for each. Afterwards it sets the
  `ImportFile`'s `row_count` and transaction date range and saves it.
- `createTransaction(row, import_file)` is **abstract** — each source subclass
  implements it. It returns the created `Transaction`, or `None` to signal the
  row was skipped (a duplicate). Only created rows count toward `row_count` and
  the date range.
- `open_rows()` yields row dicts and can be overridden when a file needs custom
  framing (Santander does — see below).

## Sign convention

`amount` is signed: **money out positive, money in negative** (see
`docs/CONVENTIONS.md`). Each source signs its raw amount to match:

| Source | Raw amount | Conversion |
|--------|-----------|------------|
| Citi | separate `Debit` / `Credit` columns | `amount = Debit - Credit` |
| Chase | signed, charges negative | negate the raw value |
| Santander | signed, deposits positive | negate the raw value |

## Idempotency strategy per source

Which dedup key a source uses depends on whether the bank gives a stable id.

### Santander — `scrapers/santander.py`

Santander detail rows carry a `Serial Num` that is unique and always present, so
it maps straight to `transaction_number`. Before creating a row the importer
checks whether that serial already exists and returns `None` if so. Exact,
simple dedup; also handles overlapping exports (e.g. a "last year" file and a
"since <date>" file that share rows).

Santander files have **two sections**: a balance-summary block, a blank line,
then the transaction detail block with a *different* header. `open_rows()` is
overridden to skip everything before the header row containing `Serial Num`, then
yield only the detail rows.

### Citi and Chase — `scrapers/citi.py`, `scrapers/chase.py`

Neither Citi nor Chase provides a transaction id, so `transaction_number` stays
`NULL` and dedup uses a **synthetic occurrence key**: `(account, date, amount,
description)` plus an occurrence index.

For each `(date, amount, description)` group the importer queries the existing DB
count **once** (cached, so rows inserted during this run don't inflate it), then
skips the first *N* occurrences it sees and creates the rest. Consequences:

- Re-running the same file → every row falls within the existing count → all
  skipped → `row_count = 0`.
- Two genuinely identical charges → both created on first import (occurrences 0
  and 1), both re-matched on re-runs.
- Overlapping files → the overlap reconciles to the same counts, no duplicates.

Chase CSVs also have a `Category` column; it is currently ignored on import (all
rows land uncategorized) but is a candidate signal for the future categorization
pass.

## Notes

- Because `createTransaction` writes as it goes (so the occurrence count sees
  prior rows), the import is not wrapped in a single transaction. A mid-file
  crash leaves partial rows and the `ImportFile` `completed=False`, so the next
  crawl does not skip it: it re-runs, the dedup skips the rows already inserted,
  and the file completes.
- `category` and `domain` are written as `NULL` by every importer.
