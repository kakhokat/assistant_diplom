import json
import os
import time

import requests

ES = os.getenv("ELASTIC_URL", "http://localhost:9200").rstrip("/")

INDEX_FILMS = os.getenv("ES_INDEX_FILMS", "movies")
INDEX_GENRES = os.getenv("ES_INDEX_GENRES", "genres")
INDEX_PERSONS = os.getenv("ES_INDEX_PERSONS", "persons")

ES_WAIT_TIMEOUT = int(os.getenv("ES_WAIT_TIMEOUT", "60"))

DATA_DIR = os.getenv("DATA_DIR", "data")


def wait_es(url: str, timeout: int = ES_WAIT_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            r.raise_for_status()
            return
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError(f"Elasticsearch not ready at {url}")


def recreate_index(name: str, mapping_file: str, bulk_file: str):
    requests.delete(f"{ES}/{name}")

    with open(mapping_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    r = requests.put(f"{ES}/{name}", json=mapping)
    r.raise_for_status()
    print(f"Index {name} created")

    with open(bulk_file, "rb") as f:
        r = requests.post(
            f"{ES}/_bulk",
            data=f,
            headers={"Content-Type": "application/x-ndjson"},
        )
    r.raise_for_status()
    print(f"Index {name}: bulk loaded")
    requests.post(f"{ES}/{name}/_refresh")


def main():
    wait_es(ES)

    recreate_index(
        INDEX_FILMS,
        os.path.join(DATA_DIR, "movies.mapping.json"),
        os.path.join(DATA_DIR, "movies.bulk.ndjson"),
    )
    recreate_index(
        INDEX_GENRES,
        os.path.join(DATA_DIR, "genres.mapping.json"),
        os.path.join(DATA_DIR, "genres.bulk.ndjson"),
    )
    recreate_index(
        INDEX_PERSONS,
        os.path.join(DATA_DIR, "persons.mapping.json"),
        os.path.join(DATA_DIR, "persons.bulk.ndjson"),
    )
    print("All indices refreshed")


if __name__ == "__main__":
    main()
