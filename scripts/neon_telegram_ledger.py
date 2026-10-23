#!/usr/bin/env python3
"""Private Neon PostgreSQL publication ledger: atomic claims and lifecycle operations.

Never place NEON_DATABASE_URL in public JavaScript or logs.
"""
import os
from contextlib import contextmanager


@contextmanager
def connection():
    import psycopg
    from psycopg.rows import dict_row
    dsn = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("NEON_DATABASE_URL is required; Supabase fallback disabled")
    with psycopg.connect(dsn, connect_timeout=12, row_factory=dict_row) as db:
        yield db


def claim(kind, ref_id, ref_date, *, validation_sent=False):
    """Only one writer acquires this event; duplicates return None."""
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO public.telegram_sent (kind,ref_id,ref_date,validation_sent)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (kind,ref_id,ref_date) DO NOTHING
                   RETURNING id,kind,ref_id,ref_date""",
                (kind, ref_id, ref_date, validation_sent),
            )
            value=cur.fetchone()
            return {k:(v.isoformat() if hasattr(v,"isoformat") else str(v) if k=="id" and v is not None else v) for k,v in value.items()} if value else None


def release(kind, ref_id, ref_date):
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                """DELETE FROM public.telegram_sent
                   WHERE kind=%s AND ref_id=%s AND ref_date=%s""",
                (kind, ref_id, ref_date),
            )
            return cur.rowcount


def records(kind, since, *, limit=500, offset=0, columns=None):
    allowed={"id","kind","ref_id","ref_date","validation_sent","sent_at",
             "selection_snapshot","delivery_status","telegram_message_id",
             "published_at","settlement_status","settlement_claimed_at",
             "validated_at","validation_message_id","validation_details"}
    fields=list(columns or ["id","ref_id","ref_date","validation_sent"])
    if not fields or not set(fields).issubset(allowed):
        raise ValueError("Unsafe ledger column selection")
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT "+",".join(fields)+""" FROM public.telegram_sent
                 WHERE kind=%s AND ref_date >= %s
                 ORDER BY ref_date ASC,id ASC LIMIT %s OFFSET %s""",
                (kind, since, max(1,min(int(limit),1000)), max(0,int(offset))),
            )
            return [{k:(v.isoformat() if hasattr(v,"isoformat") else str(v) if k=="id" and v is not None else v) for k,v in row.items()} for row in cur.fetchall()]


def mark_verified(row_id, kind, *, was_unverified=True):
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                """UPDATE public.telegram_sent SET validation_sent=true,
                   validated_at=COALESCE(validated_at,now())
                   WHERE id=%s AND kind=%s AND (%s=false OR validation_sent=false)""",
                (str(row_id), kind, was_unverified),
            )
            return cur.rowcount


def update_fields(kind, ref_id, ref_date, *, delivery_status=None,
                  telegram_message_id=None, published_at=None):
    """Restricted update for delivery status (never accepts arbitrary SQL)."""
    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                """UPDATE public.telegram_sent
                SET delivery_status=COALESCE(%s,delivery_status),
                    telegram_message_id=COALESCE(%s,telegram_message_id),
                    published_at=COALESCE(%s::timestamptz,published_at)
                WHERE kind=%s AND ref_id=%s AND ref_date=%s""",
                (delivery_status,telegram_message_id,published_at,
                 kind,ref_id,ref_date),
            )
            return cur.rowcount
