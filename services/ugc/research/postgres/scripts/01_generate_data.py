#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import random
import string
import time

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from io import StringIO
from typing import Iterable
from typing import List
from typing import Tuple
from uuid import uuid4

import psycopg

from dotenv import load_dotenv


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def rand_text(rng: random.Random, min_len: int = 80, max_len: int = 400) -> str:
    n = rng.randint(min_len, max_len)
    alphabet = string.ascii_letters + string.digits + "     .,;:!?-()"
    return "".join(rng.choice(alphabet) for _ in range(n)).strip()


@dataclass(frozen=True)
class Settings:
    pg_dsn: str
    users: int
    films: int
    likes_per_user: int
    bookmarks_per_user: int
    reviews_total: int
    batch_size: int
    seed: int
    drop: bool


def get_settings() -> Settings:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate PostgreSQL data for likes/reviews/bookmarks research."
    )
    parser.add_argument(
        "--pg-dsn",
        default=os.getenv("PG_DSN", "postgresql://app:app@localhost:5432/ugc"),
    )
    parser.add_argument("--users", type=int, default=int(os.getenv("USERS", "10000")))
    parser.add_argument("--films", type=int, default=int(os.getenv("FILMS", "2000")))
    parser.add_argument(
        "--likes-per-user", type=int, default=int(os.getenv("LIKES_PER_USER", "30"))
    )
    parser.add_argument(
        "--bookmarks-per-user",
        type=int,
        default=int(os.getenv("BOOKMARKS_PER_USER", "15")),
    )
    parser.add_argument(
        "--reviews-total", type=int, default=int(os.getenv("REVIEWS_TOTAL", "50000"))
    )
    parser.add_argument(
        "--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "20000"))
    )
    parser.add_argument("--seed", type=int, default=int(os.getenv("SEED", "42")))
    parser.add_argument(
        "--drop", action="store_true", help="Drop tables before generation"
    )
    args = parser.parse_args()

    return Settings(
        pg_dsn=args.pg_dsn,
        users=args.users,
        films=args.films,
        likes_per_user=args.likes_per_user,
        bookmarks_per_user=args.bookmarks_per_user,
        reviews_total=args.reviews_total,
        batch_size=args.batch_size,
        seed=args.seed,
        drop=bool(args.drop),
    )


DDL = """
-- likes: one rating per (user_id, film_id)
CREATE TABLE IF NOT EXISTS likes (
  user_id TEXT NOT NULL,
  film_id TEXT NOT NULL,
  value SMALLINT NOT NULL CHECK (value >= 0 AND value <= 10),
  updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (user_id, film_id)
);

CREATE INDEX IF NOT EXISTS ix_likes_film ON likes (film_id);
CREATE INDEX IF NOT EXISTS ix_likes_film_value ON likes (film_id, value);

-- bookmarks: one bookmark per (user_id, film_id)
CREATE TABLE IF NOT EXISTS bookmarks (
  user_id TEXT NOT NULL,
  film_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (user_id, film_id)
);

CREATE INDEX IF NOT EXISTS ix_bookmarks_user_created_at ON bookmarks (user_id, created_at DESC);

-- reviews
CREATE TABLE IF NOT EXISTS reviews (
  review_id UUID PRIMARY KEY,
  film_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  review_likes INTEGER NOT NULL,
  review_dislikes INTEGER NOT NULL,
  user_film_rating SMALLINT NOT NULL CHECK (user_film_rating >= 0 AND user_film_rating <= 10)
);

CREATE INDEX IF NOT EXISTS ix_reviews_film_created_at ON reviews (film_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_reviews_film_likes_created_at ON reviews (film_id, review_likes DESC, created_at DESC);
"""


def maybe_drop(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS likes")
        cur.execute("DROP TABLE IF EXISTS bookmarks")
        cur.execute("DROP TABLE IF EXISTS reviews")
    conn.commit()


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def gen_user_ids(n: int) -> List[str]:
    return [f"u{idx}" for idx in range(1, n + 1)]


def gen_film_ids(n: int) -> List[str]:
    return [f"f{idx}" for idx in range(1, n + 1)]


def copy_rows(
    conn: psycopg.Connection,
    table: str,
    columns: List[str],
    rows: Iterable[Tuple],
    batch_size: int,
) -> int:
    """
    Fast load using COPY FROM STDIN with text format.
    """
    total = 0
    cols = ",".join(columns)

    buf = StringIO()
    cur_batch = 0

    def flush() -> int:
        nonlocal buf, cur_batch
        if cur_batch == 0:
            return 0
        buf.seek(0)
        with conn.cursor() as cur:
            # psycopg3 copy
            with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:
                copy.write(buf.getvalue())
        conn.commit()
        cnt = cur_batch
        buf = StringIO()
        cur_batch = 0
        return cnt

    for row in rows:
        # Escape tab/newline for text COPY (minimal)
        out_fields = []
        for v in row:
            if v is None:
                out_fields.append(r"\N")
            elif isinstance(v, datetime):
                out_fields.append(v.isoformat())
            else:
                s = str(v)
                s = (
                    s.replace("\\", "\\\\")
                    .replace("\t", "\\t")
                    .replace("\n", "\\n")
                    .replace("\r", "\\r")
                )
                out_fields.append(s)
        buf.write("\t".join(out_fields) + "\n")
        cur_batch += 1
        if cur_batch >= batch_size:
            total += flush()

    total += flush()
    return total


def _fetch_count(cur: psycopg.Cursor, sql: str) -> int:
    """
    psycopg Cursor.fetchone() -> tuple[Any, ...] | None
    mypy ругается на индексирование без проверки None.
    """
    cur.execute(sql)
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    conn = psycopg.connect(s.pg_dsn, autocommit=False)

    # quick ping
    with conn.cursor() as cur:
        cur.execute("SELECT 1")

    if s.drop:
        print("Dropping tables likes/bookmarks/reviews ...")
        maybe_drop(conn)

    print("Ensuring schema & indexes ...")
    ensure_schema(conn)

    user_ids = gen_user_ids(s.users)
    film_ids = gen_film_ids(s.films)

    print(f"Generating data into Postgres DSN: {s.pg_dsn}")
    print(
        f"users={s.users}, films={s.films}, likes_per_user={s.likes_per_user}, "
        f"bookmarks_per_user={s.bookmarks_per_user}, reviews_total={s.reviews_total}, batch_size={s.batch_size}"
    )

    # ---- LIKES ----
    t0 = time.perf_counter()

    def likes_rows():
        now = utcnow()
        for u in user_ids:
            sampled = rng.sample(film_ids, k=min(s.likes_per_user, len(film_ids)))
            for f in sampled:
                value = rng.randint(0, 10)
                yield (u, f, value, now)

    likes_cnt = copy_rows(
        conn,
        "likes",
        ["user_id", "film_id", "value", "updated_at"],
        likes_rows(),
        batch_size=s.batch_size,
    )

    likes_dt = time.perf_counter() - t0
    print(f"LIKES: inserted {likes_cnt} in {likes_dt:.2f}s")

    # ---- BOOKMARKS ----
    t0 = time.perf_counter()

    def bookmarks_rows():
        for u in user_ids:
            sampled = rng.sample(film_ids, k=min(s.bookmarks_per_user, len(film_ids)))
            for f in sampled:
                yield (u, f, utcnow())

    bookmarks_cnt = copy_rows(
        conn,
        "bookmarks",
        ["user_id", "film_id", "created_at"],
        bookmarks_rows(),
        batch_size=s.batch_size,
    )
    bookmarks_dt = time.perf_counter() - t0
    print(f"BOOKMARKS: inserted {bookmarks_cnt} in {bookmarks_dt:.2f}s")

    # ---- REVIEWS ----
    t0 = time.perf_counter()

    def reviews_rows():
        for _ in range(s.reviews_total):
            u = rng.choice(user_ids)
            f = rng.choice(film_ids)
            yield (
                str(uuid4()),
                f,
                u,
                rand_text(rng),
                utcnow(),
                rng.randint(0, 500),
                rng.randint(0, 200),
                rng.randint(0, 10),
            )

    reviews_cnt = copy_rows(
        conn,
        "reviews",
        [
            "review_id",
            "film_id",
            "user_id",
            "text",
            "created_at",
            "review_likes",
            "review_dislikes",
            "user_film_rating",
        ],
        reviews_rows(),
        batch_size=min(s.batch_size, 10000),  # keep text batches moderate
    )
    reviews_dt = time.perf_counter() - t0
    print(f"REVIEWS: inserted {reviews_cnt} in {reviews_dt:.2f}s")

    # counts
    with conn.cursor() as cur:
        likes_total = _fetch_count(cur, "SELECT count(*) FROM likes")
        bookmarks_total = _fetch_count(cur, "SELECT count(*) FROM bookmarks")
        reviews_total = _fetch_count(cur, "SELECT count(*) FROM reviews")

    print("---- COUNTS ----")
    print(f"likes: {likes_total}")
    print(f"bookmarks: {bookmarks_total}")
    print(f"reviews: {reviews_total}")

    conn.close()


if __name__ == "__main__":
    main()
