#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import random
import statistics
import time

from dataclasses import dataclass
from typing import Callable
from typing import Dict
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
        description="Benchmark PostgreSQL read queries (preloaded data)."
    )
    parser.add_argument(
        "--pg-dsn",
        default=os.getenv("PG_DSN", "postgresql://app:app@localhost:5432/ugc"),
    )
    parser.add_argument(
        "--iters", type=int, default=int(os.getenv("READ_ITERS", "200"))
    )
    parser.add_argument(
        "--warmup", type=int, default=int(os.getenv("READ_WARMUP", "30"))
    )
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


def measure(
    name: str, fn: Callable[[], None], warmup: int, iters: int
) -> Dict[str, float | str]:
    for _ in range(warmup):
        fn()

    times_ms: List[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)

    return {
        "name": name,
        "iters": float(iters),
        "avg_ms": statistics.mean(times_ms),
        "p50_ms": percentile(times_ms, 0.50),
        "p95_ms": percentile(times_ms, 0.95),
        "max_ms": max(times_ms) if times_ms else 0.0,
    }


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    conn = psycopg.connect(s.pg_dsn)

    with conn.cursor() as cur:
        cur.execute("SELECT 1")

    # Build sampling pools from actual data
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

    # 1) list_user_likes
    def q_list_user_likes():
        u = rng.choice(user_pool)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT film_id, value FROM likes WHERE user_id=%s LIMIT 200",
                (u,),
            )
            cur.fetchall()

    # 2) film_like_dislike_counts
    def q_film_like_dislike_counts():
        f = rng.choice(film_pool)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM likes WHERE film_id=%s AND value=10", (f,)
            )
            cur.fetchone()
            cur.execute("SELECT count(*) FROM likes WHERE film_id=%s AND value=0", (f,))
            cur.fetchone()

    # 3) film_avg_rating
    def q_film_avg_rating():
        f = rng.choice(film_pool)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT avg(value)::float8, count(*) FROM likes WHERE film_id=%s", (f,)
            )
            cur.fetchone()

    # 4) list_user_bookmarks
    def q_list_user_bookmarks():
        u = rng.choice(user_pool)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT film_id, created_at FROM bookmarks WHERE user_id=%s ORDER BY created_at DESC LIMIT 200",
                (u,),
            )
            cur.fetchall()

    tests = [
        ("list_user_likes", q_list_user_likes),
        ("film_like_dislike_counts", q_film_like_dislike_counts),
        ("film_avg_rating", q_film_avg_rating),
        ("list_user_bookmarks", q_list_user_bookmarks),
    ]

    print(f"PG DSN: {s.pg_dsn}")
    print(f"Warmup: {s.warmup}, Iters: {s.iters}")
    print("---- RESULTS (ms) ----")

    for name, fn in tests:
        r = measure(name, fn, warmup=s.warmup, iters=s.iters)
        print(
            f"{name}: avg={r['avg_ms']:.2f}  p50={r['p50_ms']:.2f}  p95={r['p95_ms']:.2f}  max={r['max_ms']:.2f}"
        )

    conn.close()


if __name__ == "__main__":
    main()
