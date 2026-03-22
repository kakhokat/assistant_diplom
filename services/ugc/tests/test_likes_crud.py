import pytest

pytestmark = pytest.mark.asyncio

USER_ID = "user_id"
FILM_ID = "film_id"
VALUE = "value"
COUNT = "count"
DETAIL = "detail"

LIKES = "/likes"
LIKES_BY_USER = "/likes/by-user"
LIKES_AGGREGATES = "/likes/aggregates"


async def test_likes_create_and_get(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(
        LIKES,
        json={USER_ID: user_id, FILM_ID: film_id, VALUE: 10},
    )
    assert created.status_code == 200
    assert (
        created.json()[USER_ID],
        created.json()[FILM_ID],
        int(created.json()[VALUE]),
    ) == (user_id, film_id, 10)

    got = await client.get(LIKES, params={USER_ID: user_id, FILM_ID: film_id})
    assert got.status_code == 200
    assert (got.json()[USER_ID], got.json()[FILM_ID]) == (user_id, film_id)


async def test_likes_list_by_user_and_aggregates(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(
        LIKES,
        json={USER_ID: user_id, FILM_ID: film_id, VALUE: 10},
    )
    assert created.status_code == 200

    listed = await client.get(
        LIKES_BY_USER,
        params={USER_ID: user_id, "limit": 50, "offset": 0},
    )
    assert listed.status_code == 200
    assert any(item[FILM_ID] == film_id for item in listed.json())

    agg = await client.get(LIKES_AGGREGATES, params={FILM_ID: film_id})
    data = agg.json()
    assert agg.status_code == 200
    assert data[FILM_ID] == film_id and int(data[COUNT]) >= 1


async def test_likes_delete(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(
        LIKES,
        json={USER_ID: user_id, FILM_ID: film_id, VALUE: 10},
    )
    assert created.status_code == 200

    deleted = await client.delete(LIKES, params={USER_ID: user_id, FILM_ID: film_id})
    assert deleted.status_code == 204

    missing = await client.get(LIKES, params={USER_ID: user_id, FILM_ID: film_id})
    assert missing.status_code == 404
    assert missing.json()[DETAIL] == "like_not_found"


async def test_likes_validation_unprocessable_entity(client, ids):
    r = await client.put(
        LIKES,
        json={USER_ID: ids[USER_ID], FILM_ID: ids[FILM_ID], VALUE: 11},
    )
    assert r.status_code == 422
