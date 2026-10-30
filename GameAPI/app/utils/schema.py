"""
Tiny forward-only schema sync for deployments that already have tables.

db.create_all() creates missing TABLES but never adds new COLUMNS to existing ones. This adds any model column that
is missing from the live table (additive only: it never drops, renames or rewrites anything), which is safe to run
on every deploy and works on PostgreSQL and SQLite. NOT NULL columns must carry a server_default in the model.
"""
import logging

from sqlalchemy import inspect, text

from app import db

logger = logging.getLogger("jamesvault.schema")


def add_missing_columns():
    engine = db.engine
    dialect = engine.dialect
    inspector = inspect(engine)
    added = []
    for table in db.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue  # create_all handles whole tables
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            if not col.nullable and col.server_default is None:
                raise RuntimeError(f"{table.name}.{col.name} is NOT NULL without a server_default; cannot add it safely")
            ddl = f'ALTER TABLE {dialect.identifier_preparer.quote(table.name)} ADD COLUMN {dialect.identifier_preparer.quote(col.name)} {col.type.compile(dialect=dialect)}'
            if col.server_default is not None:
                arg = col.server_default.arg
                default = arg.compile(dialect=dialect) if hasattr(arg, "compile") else repr(str(arg)) if isinstance(arg, str) else str(arg)
                ddl += f" DEFAULT {default}"
            if not col.nullable:
                ddl += " NOT NULL"
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(f"{table.name}.{col.name}")
    if dialect.name == "postgresql":  # columns that had to become BIGINT (a Telegram user id is larger than 2^31)
        for table, column in (("audit_logs", "actor_id"),):
            with engine.begin() as conn:
                kind = conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name = :t AND column_name = :c"),
                                    {"t": table, "c": column}).scalar()
                if kind == "integer":
                    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE BIGINT'))
                    added.append(f"{table}.{column} -> bigint")
    if dialect.name == "postgresql":  # new RemoteProvider members must exist in the native enum type
        from app.models import RemoteProvider
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            have = {r[0] for r in conn.execute(text("SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'remoteprovider'"))}
            for member in RemoteProvider:
                if have and member.name not in have:
                    conn.execute(text(f"ALTER TYPE remoteprovider ADD VALUE IF NOT EXISTS '{member.name}'"))
                    added.append(f"remoteprovider.{member.name}")
    if added:
        logger.warning("added columns: %s", ", ".join(added))
    return added
