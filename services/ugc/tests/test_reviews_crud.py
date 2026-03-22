import pytest

pytestmark = pytest.mark.asyncio

USER_ID = "user_id"
FILM_ID = "film_id"
TEXT = "text"
USER_FILM_RATING = "user_film_rating"
REVIEW_ID = "review_id"
DETAIL = "detail"

REVIEWS = "/reviews"
REVIEWS_BY_FILM = "/reviews/by-film"


async def _create_review(client, user_id: str, film_id: str):
    return await client.post(
        REVIEWS,
        json={
            FILM_ID: film_id,
            USER_ID: user_id,
            TEXT: "hello",
            USER_FILM_RATING: 8,
        },
    )


async def test_reviews_create_and_get(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await _create_review(client, user_id=user_id, film_id=film_id)
    assert created.status_code in (200, 201)

    body = created.json()
    assert body[FILM_ID] == film_id and body[USER_ID] == user_id
    assert REVIEW_ID in body

    rid = body[REVIEW_ID]
    got = await client.get(REVIEWS, params={REVIEW_ID: rid})
    assert got.status_code == 200
    assert got.json()[REVIEW_ID] == rid


async def test_reviews_update(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await _create_review(client, user_id=user_id, film_id=film_id)
    rid = created.json()[REVIEW_ID]
    assert bool(rid)

    updated = await client.put(
        REVIEWS,
        params={REVIEW_ID: rid},
        json={TEXT: "upd", USER_FILM_RATING: 9},
    )
    assert updated.status_code == 200
    assert updated.json()[TEXT] == "upd"
    assert int(updated.json()[USER_FILM_RATING]) == 9


async def test_reviews_list_by_film(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await _create_review(client, user_id=user_id, film_id=film_id)
    rid = created.json()[REVIEW_ID]
    assert bool(rid)

    listed = await client.get(
        REVIEWS_BY_FILM,
        params={FILM_ID: film_id, "limit": 50, "offset": 0},
    )
    assert listed.status_code == 200
    assert any(item[REVIEW_ID] == rid for item in listed.json())


async def test_reviews_delete(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await _create_review(client, user_id=user_id, film_id=film_id)
    rid = created.json()[REVIEW_ID]
    assert bool(rid)

    deleted = await client.delete(REVIEWS, params={REVIEW_ID: rid})
    assert deleted.status_code == 204

    missing = await client.get(REVIEWS, params={REVIEW_ID: rid})
    assert missing.status_code == 404
    assert missing.json()[DETAIL] == "review_not_found"


async def test_reviews_validation_unprocessable_entity(client, ids):
    r = await client.post(
        REVIEWS,
        json={
            FILM_ID: ids[FILM_ID],
            USER_ID: ids[USER_ID],
            TEXT: "",
            USER_FILM_RATING: 99,
        },
    )
    assert r.status_code == 422
