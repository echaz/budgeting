# Data model

Personal budgeting app for tracking **spend** — where the money goes. Deposits
and income are intentionally out of scope; every `Transaction` is money out.

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
| `is_active` | `BooleanField` | Default `True`; flip off instead of deleting. |
| `created_at` | `DateTimeField` | `auto_now_add`. |

`amazon` is treated as its own account so individual Amazon purchases can be
broken out (line-item itemization is a future addition, not built yet).

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
| `category` | FK → `Category` (PROTECT) | Required — purchase type. |
| `domain` | FK → `Domain` (PROTECT) | Required — who it's for. |
| `date` | `DateField` | Transaction date. |
| `amount` | `DecimalField(10, 2)` | Unsigned; spend only, so no sign logic. |
| `description` | `CharField(255)` | Merchant / what it was. |
| `created_at` | `DateTimeField` | `auto_now_add`. |

Ordered newest-first (`-date`, `-created_at`).

## Relationships

```
Account ─┐
Category ─┼─< Transaction   (each Transaction references one of each)
Domain  ─┘
```

Every transaction is classified along two independent dimensions — **Category**
(type of purchase) and **Domain** (who it's for) — which is what lets you slice
spend both ways.

## Migrations

`core/migrations/0001_initial.py` creates all four tables. It was hand-written
(not generated), validated with `manage.py makemigrations --check --dry-run`
(reports no changes), and has been applied. See `docs/OPERATIONS.md` for how to
run migrations.

## Not yet built

- Amazon order line-item itemization.
- Reporting / rollups (spend by category, by domain, by month).
- Owner/family-member model (currently no owner on `Account`).
