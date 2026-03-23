from uuid import UUID


def test_persons_list(client):
    r = client.get("/api/v1/persons/?page_number=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert "uuid" in data[0] and "full_name" in data[0]


def test_person_details_found(client):
    pid = "11111111-1111-1111-1111-111111111111"
    r = client.get(f"/api/v1/persons/{pid}")
    assert r.status_code == 200
    payload = r.json()
    UUID(payload["id"])


def test_persons_search(client):
    r = client.get("/api/v1/persons/search?query=Alex&page_number=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert any("Alex" in i["full_name"] for i in data)
