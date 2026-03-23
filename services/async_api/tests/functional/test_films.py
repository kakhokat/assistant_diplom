from uuid import UUID


def test_films_list_sorted(client):
    r = client.get("/api/v1/films/?page_number=1&page_size=50")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # проверим сортировку по imdb_rating desc (None в конце)
    ratings = [i.get("imdb_rating") for i in data if i.get("imdb_rating") is not None]
    assert ratings == sorted(ratings, reverse=True)


def test_films_filter_by_genre(client):
    # возьмем жанр из дампа: Sci-Fi = 6f822a92-7b51-4753-8d00-ecfedf98a937
    r = client.get(
        "/api/v1/films/?genre=6f822a92-7b51-4753-8d00-ecfedf98a937&page_number=1&page_size=50"
    )
    assert r.status_code == 200
    data = r.json()
    assert all("uuid" in i and "title" in i for i in data)


def test_film_details_found(client):
    # фильм из дампа
    film_id = "b31592e5-673d-46dc-a561-9446438aea0f"
    r = client.get(f"/api/v1/films/{film_id}")
    assert r.status_code == 200
    payload = r.json()
    UUID(payload["uuid"])  # валидный UUID
    assert payload["title"]


def test_film_details_not_found(client):
    r = client.get("/api/v1/films/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_films_search(client):
    r = client.get("/api/v1/films/search?query=star&page_number=1&page_size=50")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # должно что-то найти из дампа: Lunar: The Silver Star
    assert any("Star" in i["title"] for i in data)
