from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import requests

ES_DEFAULT = os.getenv('ELASTIC_URL', 'http://localhost:9200').rstrip('/')
INDEX_FILMS = os.getenv('ES_INDEX_FILMS', 'movies')
INDEX_GENRES = os.getenv('ES_INDEX_GENRES', 'genres')
INDEX_PERSONS = os.getenv('ES_INDEX_PERSONS', 'persons')
DATA_DIR = Path(os.getenv('DATA_DIR', Path(__file__).resolve().parents[1] / 'data'))
WAIT_TIMEOUT = int(os.getenv('ES_WAIT_TIMEOUT', '60'))

MOVIE_NS = 10**12
PERSON_NS = 2 * 10**12
GENRE_NS = 3 * 10**12

EXTRA_GENRES: list[tuple[str, list[str]]] = [
    ('Триллер', ['Thriller']),
    ('Приключения', ['Adventure']),
    ('Криминал', ['Crime']),
    ('Боевик', ['Action']),
    ('Семейный', ['Family']),
    ('Анимация', ['Animation']),
    ('Фэнтези', ['Fantasy']),
    ('История', ['History']),
    ('Музыка', ['Music']),
    ('Документальный', ['Documentary']),
    ('Военный', ['War']),
    ('Биография', ['Biography']),
]

TITLE_PREFIX_RU = [
    'Тихий', 'Лунный', 'Ночной', 'Северный', 'Красный', 'Стеклянный', 'Последний', 'Скрытый', 'Громкий', 'Зимний',
    'Золотой', 'Туманный', 'Солнечный', 'Летний', 'Дальний', 'Бесконечный', 'Хрупкий', 'Быстрый', 'Тайный', 'Глубокий',
]
TITLE_CORE_RU = [
    'берег', 'маршрут', 'маяк', 'курьер', 'город', 'горизонт', 'лабиринт', 'сигнал', 'архив', 'пульс',
    'перрон', 'порт', 'ледник', 'эфир', 'спутник', 'рейс', 'след', 'ветер', 'ключ', 'код',
]
TITLE_SUFFIX_RU = [
    'полуночи', 'рассвета', 'памяти', 'тишины', 'звёзд', 'орбиты', 'причала', 'января', 'июля', 'границы',
    'легенды', 'времени', 'сезона', 'ветра', 'света', 'маршрута', 'архива', 'берега', 'города', 'эфира',
]
TITLE_TAIL_RU = [
    'у причала', 'после шторма', 'перед рассветом', 'среди огней', 'над рекой', 'на краю города', 'посреди зимы', 'в тумане',
    'под звёздами', 'на линии горизонта', 'в тишине', 'за поворотом', 'в старом порту', 'на орбите', 'после полуночи',
    'в конце июля', 'на другом берегу', 'между башнями', 'у северной станции', 'на пустой трассе',
]
TITLE_PREFIX_EN = [
    'Silent', 'Lunar', 'Night', 'Northern', 'Red', 'Glass', 'Last', 'Hidden', 'Loud', 'Winter',
    'Golden', 'Foggy', 'Solar', 'Summer', 'Distant', 'Endless', 'Fragile', 'Rapid', 'Secret', 'Deep',
]
TITLE_CORE_EN = [
    'Shore', 'Route', 'Beacon', 'Courier', 'City', 'Horizon', 'Maze', 'Signal', 'Archive', 'Pulse',
    'Platform', 'Harbor', 'Glacier', 'Ether', 'Satellite', 'Flight', 'Trace', 'Wind', 'Key', 'Code',
]
TITLE_SUFFIX_EN = [
    'Midnight', 'Dawn', 'Memory', 'Silence', 'Stars', 'Orbit', 'Pier', 'January', 'July', 'Border',
    'Legend', 'Time', 'Season', 'Wind', 'Light', 'Route', 'Archive', 'Shore', 'City', 'Ether',
]
TITLE_TAIL_EN = [
    'at the Pier', 'After the Storm', 'Before Dawn', 'Among the Lights', 'Over the River', 'at the Edge of the City',
    'in Midwinter', 'in the Fog', 'Under the Stars', 'on the Horizon Line', 'in Silence', 'Beyond the Turn',
    'in the Old Harbor', 'in Orbit', 'After Midnight', 'at the End of July', 'Across the Shore', 'Between the Towers',
    'at the Northern Station', 'on the Empty Road',
]
HEROES = ['курьер', 'студент', 'инженер', 'музыкант', 'тренер', 'архивист', 'репортёр', 'навигатор', 'следователь', 'метеоролог', 'оператор', 'историк']
SETTINGS = ['на окраине большого города', 'в северном посёлке', 'на орбитальной станции', 'в спортивной академии', 'в приморском порту', 'в старом архиве', 'в ночном поезде', 'на далёком острове']
CONFLICTS = ['ищет пропавший сигнал', 'пытается вернуть утраченную запись', 'раскрывает чужую тайну', 'готовится к решающему матчу', 'спасает команду от распада', 'разбирается в прошлом семьи', 'идёт по следу забытого дела', 'пытается остановить цепочку странных событий']
TWISTS = ['и постепенно меняет жизнь окружающих', 'и находит неожиданных союзников', 'и узнаёт, что ошибка была неслучайной', 'и сталкивается с выбором между карьерой и близкими', 'и открывает новый смысл своей работы', 'и выходит на след старой легенды', 'и понимает, что правда ближе, чем казалось', 'и вынужден довериться человеку из прошлого']
PERSON_FIRST = ['Алексей', 'Андрей', 'Илья', 'Максим', 'Денис', 'Кирилл', 'Никита', 'Егор', 'Михаил', 'Павел', 'Елена', 'Марина', 'Анна', 'Вера', 'Дарья', 'Полина', 'Луна', 'Нора', 'Мира', 'Софья', 'Татьяна', 'Алина', 'Оксана', 'Яна', 'Арина', 'Виктория', 'Степан', 'Игорь', 'Сергей', 'Роман', 'Леонид', 'Матвей', 'Владислав', 'Олег', 'Константин', 'Юлия', 'Екатерина', 'Валерия', 'Надежда', 'Галина']
PERSON_LAST = ['Северов', 'Маяков', 'Орлов', 'Ромашин', 'Белов', 'Летов', 'Ветров', 'Сильвер', 'Вейл', 'Кедров', 'Зарин', 'Островский', 'Берегов', 'Лесной', 'Громов', 'Звягин', 'Лавров', 'Яснов', 'Мельников', 'Данилин', 'Журавлёв', 'Корнеев', 'Волков', 'Березин', 'Соколов', 'Миронов', 'Рябинин', 'Крылов', 'Платонов', 'Назаров', 'Озерный', 'Чернов', 'Вишня', 'Морозов', 'Городецкий', 'Туманов', 'Светлов', 'Причалов', 'Ермаков', 'Терентьев']

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': ' ', '-': '-', '№': 'No.', ':': ':', '«': '', '»': '', '—': '-',
}


@dataclass(frozen=True)
class PersonRef:
    person_id: str
    full_name: str
    alias: str
    role: str


@dataclass(frozen=True)
class GenreRef:
    genre_id: str
    name: str
    aliases: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Генерация и загрузка большого синтетического каталога в Elasticsearch.')
    parser.add_argument('--elastic-url', default=ES_DEFAULT)
    parser.add_argument('--films', type=int, default=100_000)
    parser.add_argument('--chunk-size', type=int, default=5_000)
    parser.add_argument('--director-pool', type=int, default=20_000)
    parser.add_argument('--actor-pool', type=int, default=40_000)
    parser.add_argument('--writer-pool', type=int, default=20_000)
    parser.add_argument('--wait-timeout', type=int, default=WAIT_TIMEOUT)
    parser.add_argument('--without-base-fixtures', action='store_true')
    parser.add_argument('--skip-recreate', action='store_true')
    parser.add_argument('--refresh-only-at-end', action='store_true')
    return parser.parse_args()


def translit(value: str) -> str:
    parts: list[str] = []
    for char in value.lower():
        parts.append(TRANSLIT_MAP.get(char, char))
    result = ''.join(parts)
    return ' '.join(token.capitalize() for token in result.split())


def make_uuid(offset: int) -> str:
    return str(uuid.UUID(int=offset % (1 << 128)))


def wait_es(url: str, timeout: int) -> None:
    started = time.time()
    while time.time() - started < timeout:
        try:
            response = requests.get(url, timeout=2)
            response.raise_for_status()
            return
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError(f'Elasticsearch not ready at {url}')


def recreate_index(es_url: str, index_name: str, mapping_path: Path) -> None:
    requests.delete(f'{es_url}/{index_name}', timeout=30)
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    response = requests.put(f'{es_url}/{index_name}', json=mapping, timeout=30)
    response.raise_for_status()
    print(f'[INDEX] recreated {index_name}')


def refresh_index(es_url: str, index_name: str) -> None:
    response = requests.post(f'{es_url}/{index_name}/_refresh', timeout=30)
    response.raise_for_status()


def post_bulk(es_url: str, lines: list[str]) -> None:
    payload = ''.join(lines)
    response = requests.post(
        f'{es_url}/_bulk',
        data=payload.encode('utf-8'),
        headers={'Content-Type': 'application/x-ndjson'},
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    if result.get('errors'):
        first_error = next((item for item in result.get('items', []) if item.get('index', {}).get('error')), None)
        raise RuntimeError(f'Bulk indexing returned errors: {first_error}')


def iter_bulk_file_docs(path: Path) -> Iterator[tuple[dict, dict]]:
    lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(lines) % 2 != 0:
        raise ValueError(f'Invalid NDJSON pair count in {path}')
    for idx in range(0, len(lines), 2):
        yield json.loads(lines[idx]), json.loads(lines[idx + 1])


def load_base_fixture_bulk(es_url: str, index_name: str, bulk_path: Path) -> list[dict]:
    docs: list[dict] = []
    lines: list[str] = []
    for meta, doc in iter_bulk_file_docs(bulk_path):
        meta.setdefault('index', {})['_index'] = index_name
        lines.append(json.dumps(meta, ensure_ascii=False) + '\n')
        lines.append(json.dumps(doc, ensure_ascii=False) + '\n')
        docs.append(doc)
    post_bulk(es_url, lines)
    print(f'[BASE] loaded {len(docs)} docs into {index_name}')
    return docs


def title_capacity() -> int:
    return len(TITLE_PREFIX_RU) * len(TITLE_CORE_RU) * len(TITLE_SUFFIX_RU) * len(TITLE_TAIL_RU)


def title_components(idx: int) -> tuple[int, int, int, int]:
    prefix_idx = idx % len(TITLE_PREFIX_RU)
    idx //= len(TITLE_PREFIX_RU)
    core_idx = idx % len(TITLE_CORE_RU)
    idx //= len(TITLE_CORE_RU)
    suffix_idx = idx % len(TITLE_SUFFIX_RU)
    idx //= len(TITLE_SUFFIX_RU)
    tail_idx = idx % len(TITLE_TAIL_RU)
    return prefix_idx, core_idx, suffix_idx, tail_idx


def synthetic_title_ru(idx: int) -> str:
    p, c, s, t = title_components(idx)
    return f'{TITLE_PREFIX_RU[p]} {TITLE_CORE_RU[c]} {TITLE_SUFFIX_RU[s]} {TITLE_TAIL_RU[t]}'


def synthetic_title_en(idx: int) -> str:
    p, c, s, t = title_components(idx)
    return f'{TITLE_PREFIX_EN[p]} {TITLE_CORE_EN[c]} {TITLE_SUFFIX_EN[s]} {TITLE_TAIL_EN[t]}'


def synthetic_description(idx: int) -> str:
    hero = HEROES[idx % len(HEROES)]
    setting = SETTINGS[(idx // len(HEROES)) % len(SETTINGS)]
    conflict = CONFLICTS[(idx // (len(HEROES) * len(SETTINGS))) % len(CONFLICTS)]
    twist = TWISTS[(idx // (len(HEROES) * len(SETTINGS) * len(CONFLICTS))) % len(TWISTS)]
    return f'История о том, как {hero} {setting} {conflict} {twist}.'


def person_name(role_prefix: str, idx: int) -> str:
    role_shift = {'director': 3, 'actor': 11, 'writer': 19}.get(role_prefix, 0)
    first = PERSON_FIRST[(idx + role_shift) % len(PERSON_FIRST)]
    last_primary = PERSON_LAST[(idx // len(PERSON_FIRST)) % len(PERSON_LAST)]
    last_secondary = PERSON_LAST[(idx // (len(PERSON_FIRST) * len(PERSON_LAST))) % len(PERSON_LAST)]
    if last_secondary == last_primary:
        last_secondary = PERSON_LAST[(PERSON_LAST.index(last_primary) + role_shift + 1) % len(PERSON_LAST)]
    return f'{first} {last_primary}-{last_secondary}'


def person_ref(namespace: int, role_prefix: str, role: str, idx: int) -> PersonRef:
    full_name = person_name(role, idx)
    return PersonRef(
        person_id=make_uuid(namespace + idx + 1),
        full_name=full_name,
        alias=translit(full_name),
        role=role,
    )


def extra_genres() -> list[GenreRef]:
    refs: list[GenreRef] = []
    for idx, (name, aliases) in enumerate(EXTRA_GENRES, start=1):
        refs.append(GenreRef(genre_id=make_uuid(GENRE_NS + idx), name=name, aliases=aliases))
    return refs


def build_genre_pool(base_genres: list[dict]) -> list[GenreRef]:
    pool = [GenreRef(genre_id=str(doc['id']), name=str(doc['name']), aliases=list(doc.get('aliases') or [])) for doc in base_genres]
    pool.extend(extra_genres())
    return pool


def synthetic_movie_id(idx: int) -> str:
    return make_uuid(MOVIE_NS + idx + 1)


def director_for_movie(idx: int, director_pool: int) -> PersonRef:
    return person_ref(PERSON_NS, 'Р', 'director', idx % director_pool)


def actor_for_movie(idx: int, actor_pool: int, slot: int) -> PersonRef:
    offsets = [0, actor_pool // 3, (2 * actor_pool) // 3]
    actor_idx = (idx + offsets[slot]) % actor_pool
    return person_ref(PERSON_NS + 500_000_000, 'А', 'actor', actor_idx)


def writer_for_movie(idx: int, writer_pool: int) -> PersonRef:
    return person_ref(PERSON_NS + 900_000_000, 'С', 'writer', idx % writer_pool)


def synthetic_movie_doc(idx: int, genres: list[GenreRef], director_pool: int, actor_pool: int, writer_pool: int) -> dict:
    primary = genres[idx % len(genres)]
    secondary = genres[(idx * 7 + 3) % len(genres)]
    tertiary = genres[(idx * 11 + 5) % len(genres)]
    chosen_genres = [primary.genre_id]
    if secondary.genre_id != primary.genre_id and idx % 2 == 0:
        chosen_genres.append(secondary.genre_id)
    if tertiary.genre_id not in chosen_genres and idx % 5 == 0:
        chosen_genres.append(tertiary.genre_id)

    director = director_for_movie(idx, director_pool)
    actor_refs = [actor_for_movie(idx, actor_pool, slot) for slot in range(3)]
    unique_actor_names: list[str] = []
    seen = set()
    for actor in actor_refs:
        if actor.full_name not in seen:
            seen.add(actor.full_name)
            unique_actor_names.append(actor.full_name)
    writer = writer_for_movie(idx, writer_pool)

    ru_title = synthetic_title_ru(idx)
    en_title = synthetic_title_en(idx)
    alias_values = [en_title, translit(ru_title)]

    raw_rating = 4.15 + (((idx * 9301 + 49297) % 571) / 100)
    rating = round(min(raw_rating, 9.86), 2)
    if idx % 113 == 0:
        rating = None

    return {
        'id': synthetic_movie_id(idx),
        'title': ru_title,
        'original_title': en_title,
        'title_aliases': alias_values,
        'description': synthetic_description(idx),
        'imdb_rating': rating,
        'genre': chosen_genres,
        'runtime_minutes': 78 + (idx % 75),
        'directors': [director.full_name],
        'actors': unique_actor_names,
        'writers': [writer.full_name],
    }


def iter_synthetic_movie_docs(total: int, genres: list[GenreRef], director_pool: int, actor_pool: int, writer_pool: int) -> Iterator[dict]:
    for idx in range(total):
        yield synthetic_movie_doc(idx, genres, director_pool, actor_pool, writer_pool)


def iter_person_movie_indexes(person_idx: int, pool: int, total_films: int, offsets: Iterable[int]) -> Iterator[int]:
    seen: set[int] = set()
    for offset in offsets:
        start = (person_idx - offset) % pool
        current = start
        while current < total_films:
            if current not in seen:
                seen.add(current)
                yield current
            current += pool


def person_doc(person: PersonRef, film_indexes: Iterable[int]) -> dict:
    refs = [
        {
            'uuid': synthetic_movie_id(film_idx),
            'title': synthetic_title_ru(film_idx),
            'roles': [person.role],
        }
        for film_idx in film_indexes
    ]
    return {
        'id': person.person_id,
        'full_name': person.full_name,
        'aliases': [person.alias],
        'films': refs,
    }


def index_documents(es_url: str, index_name: str, docs: Iterator[dict], chunk_size: int, progress_label: str) -> int:
    lines: list[str] = []
    total = 0
    started = time.time()
    for doc in docs:
        doc_id = str(doc['id'])
        lines.append(json.dumps({'index': {'_index': index_name, '_id': doc_id}}, ensure_ascii=False) + '\n')
        lines.append(json.dumps(doc, ensure_ascii=False) + '\n')
        total += 1
        if total % chunk_size == 0:
            post_bulk(es_url, lines)
            elapsed = max(time.time() - started, 0.001)
            rate = total / elapsed
            print(f'[{progress_label}] indexed {total:,} docs ({rate:,.0f} docs/sec)')
            lines = []
    if lines:
        post_bulk(es_url, lines)
    elapsed = max(time.time() - started, 0.001)
    print(f'[{progress_label}] done: {total:,} docs in {elapsed:,.1f}s')
    return total


def iter_synthetic_person_docs(total_films: int, director_pool: int, actor_pool: int, writer_pool: int) -> Iterator[dict]:
    for idx in range(director_pool):
        person = person_ref(PERSON_NS, 'Р', 'director', idx)
        yield person_doc(person, iter_person_movie_indexes(idx, director_pool, total_films, [0]))
    actor_offsets = [0, actor_pool // 3, (2 * actor_pool) // 3]
    for idx in range(actor_pool):
        person = person_ref(PERSON_NS + 500_000_000, 'А', 'actor', idx)
        yield person_doc(person, iter_person_movie_indexes(idx, actor_pool, total_films, actor_offsets))
    for idx in range(writer_pool):
        person = person_ref(PERSON_NS + 900_000_000, 'С', 'writer', idx)
        yield person_doc(person, iter_person_movie_indexes(idx, writer_pool, total_films, [0]))


def index_extra_genres(es_url: str, chunk_size: int) -> list[dict]:
    docs = [
        {'id': genre.genre_id, 'name': genre.name, 'aliases': genre.aliases}
        for genre in extra_genres()
    ]
    index_documents(es_url, INDEX_GENRES, iter(docs), chunk_size=max(100, min(chunk_size, 1000)), progress_label='genres')
    return docs


def ensure_positive_odd(value: int) -> int:
    if value <= 0:
        raise ValueError('Pool size must be positive')
    return value if value % 2 == 1 else value + 1


def main() -> int:
    args = parse_args()
    director_pool = ensure_positive_odd(args.director_pool)
    actor_pool = ensure_positive_odd(args.actor_pool)
    writer_pool = ensure_positive_odd(args.writer_pool)

    capacity = title_capacity()
    if args.films > capacity:
        raise ValueError(
            f'Нельзя сгенерировать {args.films:,} фильмов без дублей названий: лимит текущего генератора {capacity:,}.'
        )

    wait_es(args.elastic_url, args.wait_timeout)

    if not args.skip_recreate:
        recreate_index(args.elastic_url, INDEX_FILMS, DATA_DIR / 'movies.mapping.json')
        recreate_index(args.elastic_url, INDEX_GENRES, DATA_DIR / 'genres.mapping.json')
        recreate_index(args.elastic_url, INDEX_PERSONS, DATA_DIR / 'persons.mapping.json')

    base_genres: list[dict] = []
    if not args.without_base_fixtures:
        load_base_fixture_bulk(args.elastic_url, INDEX_FILMS, DATA_DIR / 'movies.bulk.ndjson')
        base_genres = load_base_fixture_bulk(args.elastic_url, INDEX_GENRES, DATA_DIR / 'genres.bulk.ndjson')
        load_base_fixture_bulk(args.elastic_url, INDEX_PERSONS, DATA_DIR / 'persons.bulk.ndjson')

    extra_genre_docs = index_extra_genres(args.elastic_url, args.chunk_size)
    genre_pool = build_genre_pool(base_genres + extra_genre_docs)

    movie_count = index_documents(
        args.elastic_url,
        INDEX_FILMS,
        iter_synthetic_movie_docs(args.films, genre_pool, director_pool, actor_pool, writer_pool),
        chunk_size=args.chunk_size,
        progress_label='movies',
    )
    person_count = index_documents(
        args.elastic_url,
        INDEX_PERSONS,
        iter_synthetic_person_docs(args.films, director_pool, actor_pool, writer_pool),
        chunk_size=max(500, min(args.chunk_size, 2_000)),
        progress_label='persons',
    )

    if not args.refresh_only_at_end:
        refresh_index(args.elastic_url, INDEX_FILMS)
        refresh_index(args.elastic_url, INDEX_GENRES)
        refresh_index(args.elastic_url, INDEX_PERSONS)
    else:
        for index_name in (INDEX_FILMS, INDEX_GENRES, INDEX_PERSONS):
            refresh_index(args.elastic_url, index_name)

    print('[SUMMARY] synthetic catalog is ready')
    print(f'  movies indexed:  {movie_count:,}')
    print(f'  persons indexed: {person_count:,}')
    print(f'  genres available: {len(genre_pool):,}')
    print(f'  director pool: {director_pool:,}')
    print(f'  actor pool:    {actor_pool:,}')
    print(f'  writer pool:   {writer_pool:,}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
