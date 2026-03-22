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
from typing import Iterable
from typing import List
from typing import Tuple
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def rand_text(rng: random.Random, min_len: int = 80, max_len: int = 400) -> str:
    n = rng.randint(min_len, max_len)
    alphabet = string.ascii_letters + string.digits + "     .,;:!?-()"
    return "".join(rng.choice(alphabet) for _ in range(n)).strip()


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    db_name: str
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
        description="Generate MongoDB data for likes/reviews/bookmarks research."
    )
    parser.add_argument(
        "--mongo-uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017")
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "ugc"))
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
        "--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "1000"))
    )
    parser.add_argument("--seed", type=int, default=int(os.getenv("SEED", "42")))
    parser.add_argument(
        "--drop", action="store_true", help="Drop collections before generation"
    )
    args = parser.parse_args()

    return Settings(
        mongo_uri=args.mongo_uri,
        db_name=args.db,
        users=args.users,
        films=args.films,
        likes_per_user=args.likes_per_user,
        bookmarks_per_user=args.bookmarks_per_user,
        reviews_total=args.reviews_total,
        batch_size=args.batch_size,
        seed=args.seed,
        drop=bool(args.drop),
    )


def connect(mongo_uri: str) -> MongoClient:
    # serverSelectionTimeoutMS helps fail fast if Mongo isn't up
    return MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)


def ensure_indexes(db) -> None:
    likes: Collection = db.likes
    bookmarks: Collection = db.bookmarks
    reviews: Collection = db.reviews

    # likes: one rating per (user, film)
    likes.create_index(
        [("user_id", 1), ("film_id", 1)], unique=True, name="ux_likes_user_film"
    )
    likes.create_index([("film_id", 1), ("value", 1)], name="ix_likes_film_value")
    likes.create_index([("film_id", 1)], name="ix_likes_film")

    # bookmarks: one bookmark per (user, film)
    bookmarks.create_index(
        [("user_id", 1), ("film_id", 1)], unique=True, name="ux_bookmarks_user_film"
    )
    bookmarks.create_index(
        [("user_id", 1), ("created_at", -1)], name="ix_bookmarks_user_created_at"
    )

    # reviews
    reviews.create_index(
        [("film_id", 1), ("created_at", -1)], name="ix_reviews_film_created_at"
    )
    reviews.create_index(
        [("film_id", 1), ("review_likes", -1), ("created_at", -1)],
        name="ix_reviews_film_likes_created_at",
    )
    reviews.create_index([("review_id", 1)], unique=True, name="ux_reviews_review_id")


def maybe_drop(db) -> None:
    for name in ("likes", "bookmarks", "reviews"):
        db[name].drop()


def gen_user_ids(n: int) -> List[str]:
    return [f"u{idx}" for idx in range(1, n + 1)]


def gen_film_ids(n: int) -> List[str]:
    return [f"f{idx}" for idx in range(1, n + 1)]


def chunked(it: Iterable, size: int):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def upsert_likes(
    db,
    user_ids: List[str],
    film_ids: List[str],
    likes_per_user: int,
    batch_size: int,
    rng: random.Random,
) -> Tuple[int, float]:
    likes: Collection = db.likes
    total_ops = 0
    t0 = time.perf_counter()

    for u in user_ids:
        # sample films for this user without repetition
        sampled = rng.sample(film_ids, k=min(likes_per_user, len(film_ids)))
        ops = []
        now = utcnow()
        for f in sampled:
            value = rng.randint(0, 10)  # smallint-like range
            ops.append(
                UpdateOne(
                    {"user_id": u, "film_id": f},
                    {"$set": {"value": value, "updated_at": now}},
                    upsert=True,
                )
            )
        for part in chunked(ops, batch_size):
            try:
                res = likes.bulk_write(part, ordered=False)
                total_ops += res.upserted_count + res.modified_count + res.matched_count
            except BulkWriteError as e:
                # If duplicates happen due to retries or race, we ignore; but with unique index + upsert it should be fine.
                total_ops += len(part)

    dt = time.perf_counter() - t0
    return total_ops, dt


def upsert_bookmarks(
    db,
    user_ids: List[str],
    film_ids: List[str],
    bookmarks_per_user: int,
    batch_size: int,
    rng: random.Random,
) -> Tuple[int, float]:
    bookmarks: Collection = db.bookmarks
    total_ops = 0
    t0 = time.perf_counter()

    for u in user_ids:
        sampled = rng.sample(film_ids, k=min(bookmarks_per_user, len(film_ids)))
        ops = []
        for f in sampled:
            ops.append(
                UpdateOne(
                    {"user_id": u, "film_id": f},
                    {"$setOnInsert": {"created_at": utcnow()}},
                    upsert=True,
                )
            )
        for part in chunked(ops, batch_size):
            try:
                res = bookmarks.bulk_write(part, ordered=False)
                total_ops += res.upserted_count + res.modified_count + res.matched_count
            except BulkWriteError:
                total_ops += len(part)

    dt = time.perf_counter() - t0
    return total_ops, dt


def insert_reviews(
    db,
    user_ids: List[str],
    film_ids: List[str],
    reviews_total: int,
    batch_size: int,
    rng: random.Random,
) -> Tuple[int, float]:
    reviews: Collection = db.reviews
    total = 0
    t0 = time.perf_counter()

    docs = []
    for _ in range(reviews_total):
        u = rng.choice(user_ids)
        f = rng.choice(film_ids)
        docs.append(
            {
                "review_id": str(uuid4()),
                "film_id": f,
                "user_id": u,
                "text": rand_text(rng),
                "created_at": utcnow(),
                "review_likes": rng.randint(0, 500),
                "review_dislikes": rng.randint(0, 200),
                "user_film_rating": rng.randint(0, 10),
            }
        )
        if len(docs) >= batch_size:
            reviews.insert_many(docs, ordered=False)
            total += len(docs)
            docs = []

    if docs:
        reviews.insert_many(docs, ordered=False)
        total += len(docs)

    dt = time.perf_counter() - t0
    return total, dt


def main() -> None:
    s = get_settings()
    rng = random.Random(s.seed)

    client = connect(s.mongo_uri)
    db = client[s.db_name]

    # fail fast if cannot connect
    client.admin.command("ping")

    if s.drop:
        print("Dropping collections likes/bookmarks/reviews ...")
        maybe_drop(db)

    print("Ensuring indexes ...")
    ensure_indexes(db)

    user_ids = gen_user_ids(s.users)
    film_ids = gen_film_ids(s.films)

    print(f"Generating data into DB '{s.db_name}' on {s.mongo_uri}")
    print(
        f"users={s.users}, films={s.films}, likes_per_user={s.likes_per_user}, "
        f"bookmarks_per_user={s.bookmarks_per_user}, reviews_total={s.reviews_total}, batch_size={s.batch_size}"
    )

    likes_ops, likes_dt = upsert_likes(
        db, user_ids, film_ids, s.likes_per_user, s.batch_size, rng
    )
    print(f"LIKES: completed (approx ops={likes_ops}) in {likes_dt:.2f}s")

    b_ops, b_dt = upsert_bookmarks(
        db, user_ids, film_ids, s.bookmarks_per_user, s.batch_size, rng
    )
    print(f"BOOKMARKS: completed (approx ops={b_ops}) in {b_dt:.2f}s")

    r_cnt, r_dt = insert_reviews(
        db, user_ids, film_ids, s.reviews_total, s.batch_size, rng
    )
    print(f"REVIEWS: inserted {r_cnt} in {r_dt:.2f}s")

    # summary counts
    likes_cnt = db.likes.estimated_document_count()
    bookmarks_cnt = db.bookmarks.estimated_document_count()
    reviews_cnt = db.reviews.estimated_document_count()

    print("---- COUNTS ----")
    print(f"likes: {likes_cnt}")
    print(f"bookmarks: {bookmarks_cnt}")
    print(f"reviews: {reviews_cnt}")

    client.close()


if __name__ == "__main__":
    main()
