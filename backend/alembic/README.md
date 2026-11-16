# Migration chain

## Current state

A single baseline revision, `a43d5ef44075`, creates the entire schema from the
models. On an empty database:

    alembic upgrade head

That is the whole disaster-recovery path. No `create_all`, no manual step to
forget while restoring under pressure.

Verified: 71 tables, 978 columns, zero differences in type or nullability
against the live schema, and `scripts/check_schema_drift.py` exits 0.

## Why the history was squashed

The previous chain could not build a database: its root revision was empty and
the schema was really created by `Base.metadata.create_all` at startup. Only
30 of 91 revisions contained `create_table` at all. `alembic upgrade head`
on an empty database failed, so CI ran `create_all` and then compared the
result against the same models - a tautology that always passed.

The root cause of the gaps: `env.py` used `from app.models import *`, which
registers only what `__init__` exports, so autogenerate never saw 11 tables.
It now walks every module.

## The archive, and what it can NOT do

`versions_archive/` keeps all 95 pre-squash revisions. Read them with:

    alembic -c alembic/archive.ini heads
    alembic -c alembic/archive.ini history

A database that genuinely traversed the old chain can be brought forward:

    alembic -c alembic/archive.ini upgrade head
    alembic stamp a43d5ef44075

**Limitation, verified not assumed:** a database whose schema was built by
`create_all` can NOT be walked through the archive. Stamping it at an old
revision and upgrading fails with `DuplicateColumn` (for example
`companies.edo_operator`), because those revisions expect to add columns that
`create_all` already made. For such a database, verify the schema with
`scripts/check_schema_drift.py` and then `alembic stamp a43d5ef44075`.

## Adding a migration

    alembic revision --autogenerate -m "what and why"

Review the output. Autogenerate does not detect every change, and it now sees
all models - but it still will not rename a column or split a table for you.

Then check both directions:

    alembic upgrade head
    alembic downgrade -1
    alembic upgrade head
