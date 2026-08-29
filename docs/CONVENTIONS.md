# Project conventions

## Models

- **All `ForeignKey` fields use `on_delete=models.PROTECT`.** Deleting a row
  that other records point at must fail loudly rather than silently cascade or
  null out spend history. Choose a different `on_delete` only with a deliberate,
  documented reason.
