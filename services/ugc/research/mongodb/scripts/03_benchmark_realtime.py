#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import random
import statistics
import time

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import List
from typing import Mapping
from typing import Sequence
from typing import Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo import ReturnDocument


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        description=(
            "Benchmark realtime scenario: upsert like/dislike/rating "
            "and immediately read aggregates."
        )
    )
    parser.add_argument(
        "--mongo-uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017")
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "ugc"))
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


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    client = connect(s.mongo_uri)
    db = client[s.db_name]
    client.admin.command("ping")

    likes = db.likes

    # Prepare sampling pools from existing data
    user_ids = likes.distinct("user_id")
    film_ids = likes.distinct("film_id")
    if not user_ids or not film_ids:
        raise RuntimeError("No data found in likes. Run 01_generate_data.py first.")

    rng.shuffle(user_ids)
    rng.shuffle(film_ids)
    user_pool = user_ids[: min(s.sample_users, len(user_ids))]
    film_pool = film_ids[: min(s.sample_films, len(film_ids))]

    def write_like(u: str, f: str, value: int) -> None:
        likes.find_one_and_update(
            {"user_id": u, "film_id": f},
            {"$set": {"value": value, "updated_at": utcnow()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def read_aggregates(f: str) -> Tuple[int, int, float]:
        # counts for like/dislike (10 and 0) + avg rating for the film
        like_cnt = likes.count_documents({"film_id": f, "value": 10})
        dislike_cnt = likes.count_documents({"film_id": f, "value": 0})

        pipeline: Sequence[Mapping[str, Any]] = [
            {"$match": {"film_id": f}},
            {
                "$group": {
                    "_id": "$film_id",
                    "avg": {"$avg": "$value"},
                    "cnt": {"$sum": 1},
                }
            },
        ]
        agg = list(likes.aggregate(pipeline, allowDiskUse=False))
        avg = float(agg[0]["avg"]) if agg else 0.0
        return like_cnt, dislike_cnt, avg

    # Warmup
    for _ in range(s.warmup):
        u = rng.choice(user_pool)
        f = rng.choice(film_pool)
        value = rng.randint(0, 10)
        write_like(u, f, value)
        read_aggregates(f)

    # Measure
    times_ms: List[float] = []
    for _ in range(s.iters):
        u = rng.choice(user_pool)
        f = rng.choice(film_pool)
        value = rng.randint(0, 10)

        t0 = time.perf_counter()
        write_like(u, f, value)
        read_aggregates(f)
        dt = (time.perf_counter() - t0) * 1000.0
        times_ms.append(dt)

    avg = statistics.mean(times_ms)
    p50 = percentile(times_ms, 0.50)
    p95 = percentile(times_ms, 0.95)
    mx = max(times_ms) if times_ms else 0.0

    print(f"Mongo URI: {s.mongo_uri}")
    print(f"DB: {s.db_name}")
    print(f"Warmup: {s.warmup}, Iters: {s.iters}")
    print("---- REALTIME write+read (ms) ----")
    print(f"avg={avg:.2f}  p50={p50:.2f}  p95={p95:.2f}  max={mx:.2f}")

    client.close()


if __name__ == "__main__":
    main()
