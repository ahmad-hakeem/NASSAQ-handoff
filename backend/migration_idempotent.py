"""Idempotency helpers for Alembic migrations.

These let a migration's ``upgrade()`` skip creating an object that already
exists in the target database. This is required because some deployments were
bulk-created from the ORM models (full schema present) but stamped at an older
Alembic revision, so a plain ``alembic upgrade head`` would try to re-create
objects that are already there and abort the deploy.

Guards check existence *before* the DDL runs (via a fresh Inspector), so they
never rely on catching an error mid-transaction (which would poison the
transaction in PostgreSQL). On a fresh database nothing exists, so every guard
passes through and all objects are created normally.
"""
from alembic import op
from sqlalchemy import inspect


def _inspector(bind=None):
    return inspect(bind or op.get_bind())


def has_table(table_name, bind=None):
    return _inspector(bind).has_table(table_name)


def has_column(table_name, column_name, bind=None):
    insp = _inspector(bind)
    if not insp.has_table(table_name):
        return False
    return any(c["name"] == column_name for c in insp.get_columns(table_name))


def has_index(table_name, index_name, bind=None):
    insp = _inspector(bind)
    if not insp.has_table(table_name):
        return False
    return any(ix["name"] == index_name for ix in insp.get_indexes(table_name))


def has_constraint(table_name, constraint_name, bind=None):
    """True if a unique / primary-key / foreign-key / check constraint with this
    name exists on the table."""
    insp = _inspector(bind)
    if not insp.has_table(table_name):
        return False
    names = set()
    for uc in insp.get_unique_constraints(table_name):
        if uc.get("name"):
            names.add(uc["name"])
    pk = insp.get_pk_constraint(table_name)
    if pk and pk.get("name"):
        names.add(pk["name"])
    for fk in insp.get_foreign_keys(table_name):
        if fk.get("name"):
            names.add(fk["name"])
    try:
        for ck in insp.get_check_constraints(table_name):
            if ck.get("name"):
                names.add(ck["name"])
    except NotImplementedError:
        pass
    return constraint_name in names
