import pytest

pytestmark = pytest.mark.asyncio

USER_ID = "user_id"
FILM_ID = "film_id"
DETAIL = "detail"

BOOKMARKS = "/bookmarks"
BOOKMARKS_BY_USER = "/bookmarks/by-user"


async def test_bookmarks_create_and_get(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(BOOKMARKS, json={USER_ID: user_id, FILM_ID: film_id})
    assert created.status_code == 200
    assert (created.json()[USER_ID], created.json()[FILM_ID]) == (user_id, film_id)

    got = await client.get(BOOKMARKS, params={USER_ID: user_id, FILM_ID: film_id})
    assert got.status_code == 200
    assert (got.json()[USER_ID], got.json()[FILM_ID]) == (user_id, film_id)


async def test_bookmarks_list_by_user(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(BOOKMARKS, json={USER_ID: user_id, FILM_ID: film_id})
    assert created.status_code == 200

    listed = await client.get(
        BOOKMARKS_BY_USER,
        params={USER_ID: user_id, "limit": 50, "offset": 0},
    )
    assert listed.status_code == 200
    assert any(item[FILM_ID] == film_id for item in listed.json())


async def test_bookmarks_delete(client, ids):
    user_id = ids[USER_ID]
    film_id = ids[FILM_ID]

    created = await client.put(BOOKMARKS, json={USER_ID: user_id, FILM_ID: film_id})
    assert created.status_code == 200

    deleted = await client.delete(
        BOOKMARKS, params={USER_ID: user_id, FILM_ID: film_id}
    )
    assert deleted.status_code == 204

    missing = await client.get(BOOKMARKS, params={USER_ID: user_id, FILM_ID: film_id})
    assert missing.status_code == 404
    assert missing.json()[DETAIL] == "bookmark_not_found"
