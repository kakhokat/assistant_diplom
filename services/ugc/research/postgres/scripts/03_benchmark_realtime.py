#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import random
import statistics
import time

from dataclasses import dataclass
from typing import List

import psycopg

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    pg_dsn: str
    iters: int
    warmup: int
    seed: int
    sample_users: int
    sample_films: int


def get_settings() -> Settings:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Benchmark realtime scenario: upsert like and immediately read aggregates."
    )
    parser.add_argument(
        "--pg-dsn",
        default=os.getenv("PG_DSN", "postgresql://app:app@localhost:5432/ugc"),
    )
    parser.add_argument("--iters", type=int, default=int(os.getenv("RT_ITERS", "300")))
    parser.add_argument("--warmup", type=int, default=int(os.getenv("RT_WARMUP", "50")))
    parser.add_argument("--seed", type=int, default=int(os.getenv("SEED", "42")))
    parser.add_argument(
        "--sample-users", type=int, default=int(os.getenv("SAMPLE_USERS", "200"))
    )
    parser.add_argument(
        "--sample-films", type=int, default=int(os.getenv("SAMPLE_FILMS", "200"))
    )
    args = parser.parse_args()

    return Settings(
        pg_dsn=args.pg_dsn,
        iters=args.iters,
        warmup=args.warmup,
        seed=args.seed,
        sample_users=args.sample_users,
        sample_films=args.sample_films,
    )


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    conn = psycopg.connect(s.pg_dsn)

    with conn.cursor() as cur:
        cur.execute("SELECT 1")

    # sample pools
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT user_id FROM likes LIMIT %s", (max(s.sample_users, 50),)
        )
        user_pool = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT DISTINCT film_id FROM likes LIMIT %s", (max(s.sample_films, 50),)
        )
        film_pool = [r[0] for r in cur.fetchall()]

    if not user_pool or not film_pool:
        raise RuntimeError("No data found in likes. Run 01_generate_data.py first.")

    upsert_sql = """
    INSERT INTO likes(user_id, film_id, value, updated_at)
    VALUES (%s, %s, %s, now())
    ON CONFLICT (user_id, film_id)
    DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """

    cnt_like_sql = "SELECT count(*) FROM likes WHERE film_id=%s AND value=10"
    cnt_dislike_sql = "SELECT count(*) FROM likes WHERE film_id=%s AND value=0"
    avg_sql = "SELECT avg(value)::float8, count(*) FROM likes WHERE film_id=%s"

    def write_like(u: str, f: str, v: int) -> None:
        with conn.cursor() as cur:
            cur.execute(upsert_sql, (u, f, v))
        conn.commit()

    def read_aggs(f: str) -> None:
        with conn.cursor() as cur:
            cur.execute(cnt_like_sql, (f,))
            cur.fetchone()
            cur.execute(cnt_dislike_sql, (f,))
            cur.fetchone()
            cur.execute(avg_sql, (f,))
            cur.fetchone()

    # warmup
    for _ in range(s.warmup):
        u = rng.choice(user_pool)
        f = rng.choice(film_pool)
        v = rng.randint(0, 10)
        write_like(u, f, v)
        read_aggs(f)

    # measure
    times_ms: List[float] = []
    for _ in range(s.iters):
        u = rng.choice(user_pool)
        f = rng.choice(film_pool)
        v = rng.randint(0, 10)

        t0 = time.perf_counter()
        write_like(u, f, v)
        read_aggs(f)
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)

    avg = statistics.mean(times_ms)
    p50 = percentile(times_ms, 0.50)
    p95 = percentile(times_ms, 0.95)
    mx = max(times_ms) if times_ms else 0.0

    print(f"PG DSN: {s.pg_dsn}")
    print(f"Warmup: {s.warmup}, Iters: {s.iters}")
    print("---- REALTIME write+read (ms) ----")
    print(f"avg={avg:.2f}  p50={p50:.2f}  p95={p95:.2f}  max={mx:.2f}")

    conn.close()


if __name__ == "__main__":
    main()
