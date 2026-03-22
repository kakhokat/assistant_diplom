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
from typing import Tuple

from dotenv import load_dotenv
from pymongo import MongoClient


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    db_name: str
    iters: int
    warmup: int
    seed: int
    sample_users: int
    sample_films: int


def get_settings() -> Settings:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Benchmark MongoDB read queries (preloaded data)."
    )
    parser.add_argument(
        "--mongo-uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017")
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "ugc"))
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
        mongo_uri=args.mongo_uri,
        db_name=args.db,
        iters=args.iters,
        warmup=args.warmup,
        seed=args.seed,
        sample_users=args.sample_users,
        sample_films=args.sample_films,
    )


def connect(mongo_uri: str) -> MongoClient:
    return MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)


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
    name: str,
    fn: Callable[[], None],
    warmup: int,
    iters: int,
) -> Dict[str, float | str]:
    # warmup (not measured)
    for _ in range(warmup):
        fn()

    times_ms: List[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)

    avg = statistics.mean(times_ms)
    p50 = percentile(times_ms, 0.50)
    p95 = percentile(times_ms, 0.95)
    mx = max(times_ms) if times_ms else 0.0

    return {
        "name": name,
        "iters": float(iters),
        "avg_ms": avg,
        "p50_ms": p50,
        "p95_ms": p95,
        "max_ms": mx,
    }


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    client = connect(s.mongo_uri)
    db = client[s.db_name]
    client.admin.command("ping")

    likes = db.likes
    bookmarks = db.bookmarks

    # Prepare sampling pools from existing data to avoid querying non-existent ids
    user_ids = likes.distinct("user_id")
    film_ids = likes.distinct("film_id")
    if not user_ids or not film_ids:
        raise RuntimeError("No data found in likes. Run 01_generate_data.py first.")

    rng.shuffle(user_ids)
    rng.shuffle(film_ids)
    user_pool = user_ids[: min(s.sample_users, len(user_ids))]
    film_pool = film_ids[: min(s.sample_films, len(film_ids))]

    # 1) List of liked films by user (likes list)
    def q_user_likes_list() -> None:
        u = rng.choice(user_pool)
        list(
            likes.find({"user_id": u}, {"_id": 0, "film_id": 1, "value": 1}).limit(200)
        )

    # 2) Count likes/dislikes for film (value=10 and value=0)
    def q_film_like_dislike_counts() -> None:
        f = rng.choice(film_pool)
        likes.count_documents({"film_id": f, "value": 10})
        likes.count_documents({"film_id": f, "value": 0})

    # 3) Average user rating for film
    def q_film_avg_rating() -> None:
        f = rng.choice(film_pool)
        pipeline = [
            {"$match": {"film_id": f}},
            {
                "$group": {
                    "_id": "$film_id",
                    "avg": {"$avg": "$value"},
                    "cnt": {"$sum": 1},
                }
            },
        ]
        list(likes.aggregate(pipeline, allowDiskUse=False))

    # 4) Bookmarks list
    def q_user_bookmarks_list() -> None:
        u = rng.choice(user_pool)
        list(
            bookmarks.find({"user_id": u}, {"_id": 0, "film_id": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(200)
        )

    tests: List[Tuple[str, Callable[[], None]]] = [
        ("list_user_likes", q_user_likes_list),
        ("film_like_dislike_counts", q_film_like_dislike_counts),
        ("film_avg_rating", q_film_avg_rating),
        ("list_user_bookmarks", q_user_bookmarks_list),
    ]

    print(f"Mongo URI: {s.mongo_uri}")
    print(f"DB: {s.db_name}")
    print(f"Warmup: {s.warmup}, Iters: {s.iters}")
    print("---- RESULTS (ms) ----")

    for name, fn in tests:
        r = measure(name, fn, warmup=s.warmup, iters=s.iters)
        print(
            f"{name}: avg={float(r['avg_ms']):.2f}  "
            f"p50={float(r['p50_ms']):.2f}  "
            f"p95={float(r['p95_ms']):.2f}  "
            f"max={float(r['max_ms']):.2f}"
        )

    client.close()


if __name__ == "__main__":
    main()
