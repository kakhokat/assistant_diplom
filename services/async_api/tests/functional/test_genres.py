from uuid import UUID


def test_genres_list(client):
    r = client.get("/api/v1/genres/?page_number=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert "uuid" in data[0] and "name" in data[0]


def test_genre_details_found(client):
    gid = "00f74939-18b1-42e4-b541-b52f667d50d9"  # Drama
    r = client.get(f"/api/v1/genres/{gid}")
    assert r.status_code == 200
    payload = r.json()
    UUID(payload["id"])


def test_genres_search(client):
    r = client.get("/api/v1/genres/search?query=Drama&page_number=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert any(i["name"].lower() == "drama" for i in data)
