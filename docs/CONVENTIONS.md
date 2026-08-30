# Project conventions

## Models

- **All `ForeignKey` fields use `on_delete=models.PROTECT`.** Deleting a row
  that other records point at must fail loudly rather than silently cascade or
  null out spend history. Choose a different `on_delete` only with a deliberate,
  documented reason.

## Amounts

- **`Transaction.amount` is signed: money out is positive, money in is
  negative.** Payments, refunds, and deposits are negative. Every CSV importer
  converts its source's native signing to this convention — see
  `docs/IMPORTS.md`.
