# Data model

Personal budgeting app for tracking **spend** — where the money goes. The focus
is money out, but transactions are imported wholesale from bank/card CSVs, so
credits (payments, refunds, deposits) are captured too. `amount` is **signed**:
money out is positive, money in is negative. See `docs/CONVENTIONS.md` for the
sign convention and `docs/IMPORTS.md` for the CSV importers.

All models live in `core/models.py` and are registered in the Django admin
(`core/admin.py`). Per `docs/CONVENTIONS.md`, every `ForeignKey` uses
`on_delete=PROTECT`.

## Models

### Account
A financial account you spend from.

| Field | Type | Notes |
|-------|------|-------|
| `institution` | `CharField(100)` | Free text for now, e.g. "Citi", "Chase". |
| `account_type` | `CharField(20)` choices | `credit_card`, `savings`, `amazon`. |
| `nickname` | `CharField(100)` | Display name, e.g. "Citi Double Cash". |
| `statements_dir` | `CharField(255)` blank | Directory of CSV statements to crawl for this account (relative to project root or absolute). See `docs/IMPORTS.md`. |
| `is_active` | `BooleanField` | Default `True`; flip off instead of deleting. |
| `created_at` | `DateTimeField` | `auto_now_add`. |

`amazon` is treated as its own account so individual Amazon purchases can be
broken out (line-item itemization is a future addition, not built yet).

### ImportFile
One row per CSV file ingested. Transactions are locked to the file they came
from so an import can be audited and, if needed, corrected or unwound in bulk.

| Field | Type | Notes |
|-------|------|-------|
| `account` | FK → `Account` (PROTECT) | Which account the file was exported from. |
| `filename` | `CharField(255)` | Basename of the imported file. |
| `row_count` | `PositiveIntegerField` | Transactions actually created (dupes skipped are not counted). |
| `transaction_start_date` | `DateField` null | Earliest transaction date in the file. |
| `transaction_end_date` | `DateField` null | Latest transaction date in the file. |
| `completed` | `BooleanField` | Set `True` when the import finishes. A crawl skips any file whose `(account, filename)` already has a completed import. |
| `created_at` | `DateTimeField` | `auto_now_add`. |

The date range is nullable and filled in after the rows are created (so it can
be fixed in post). `completed` is the file-level "seen it before" guard — see
`docs/IMPORTS.md`.

### Category — dimension 1: *type of purchase*
What the money was spent on, e.g. groceries, gas, restaurant.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `CharField(100)` unique | Kept unique so the taxonomy stays clean. |

### Domain — dimension 2: *who the money is spent on*
The person/target the spend is for, e.g. self, spouse, a child, household.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `CharField(100)` unique | |

### Transaction
A single charge. Carries both category dimensions.

| Field | Type | Notes |
|-------|------|-------|
| `account` | FK → `Account` (PROTECT) | |
| `category` | FK → `Category` (PROTECT) | **Nullable** — left blank on import, filled in later by a human/AI categorization pass. |
| `domain` | FK → `Domain` (PROTECT) | **Nullable** — same as `category`. |
| `import_file` | FK → `ImportFile` (PROTECT) | Required — the CSV this row came from. |
| `transaction_number` | `CharField(100)` unique, null | Bank-provided transaction id where one exists (e.g. Santander `Serial Num`). `NULL` for sources with no id (Citi, Chase). Unique, so it enforces dedup only on rows that have one. |
| `date` | `DateField` | Transaction date. |
| `amount` | `DecimalField(10, 2)` | **Signed:** money out positive, money in (payments/refunds/deposits) negative. |
| `description` | `CharField(255)` | Merchant / what it was. |
| `created_at` | `DateTimeField` | `auto_now_add`. |

Ordered newest-first (`-date`, `-created_at`).

`transaction_number` is unique but nullable: Postgres treats `NULL`s as
distinct, so uniqueness is enforced only where an id is present. Sources without
an id rely on a synthetic occurrence key instead — see `docs/IMPORTS.md`.

## Relationships

```
Account   ─┬─< Transaction   (each Transaction references one Account)
Category  ─┤                 (Category / Domain are nullable until categorized)
Domain    ─┤
ImportFile─┘

Account ─< ImportFile        (each file belongs to one Account)
```

Every transaction is classified along two independent dimensions — **Category**
(type of purchase) and **Domain** (who it's for) — which is what lets you slice
spend both ways. Both are populated after import, not at ingest time.

## Migrations

- `core/migrations/0001_initial.py` — creates `Account`, `Category`, `Domain`,
  `Transaction`. Hand-written (not generated), validated with
  `manage.py makemigrations --check --dry-run`.
- `core/migrations/0002_transaction_transaction_number_and_more.py` — adds
  `ImportFile`, the `Transaction.import_file` FK and `transaction_number`, and
  makes `category`/`domain` nullable. Generated.
- `core/migrations/0003_account_statements_dir.py` — adds
  `Account.statements_dir`. Generated.
- `core/migrations/0004_importfile_completed.py` — adds `ImportFile.completed`.
  Generated.

See `docs/OPERATIONS.md` for how to run migrations.

## Not yet built

- Human/AI categorization pass to fill in `category` and `domain`.
- Amazon order line-item itemization.
- Reporting / rollups (spend by category, by domain, by month).
- Owner/family-member model (currently no owner on `Account`).
