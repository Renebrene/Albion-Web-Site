"""Benchmark embeddings and local chat models on ~50 queries.

Read-only for the database. Results are printed and written to
``tmp/bench_chat_models.json``.

Usage:
    .venv/bin/python scripts/bench_chat_models.py
    .venv/bin/python scripts/bench_chat_models.py --extract-limit 50
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

from backend.chat import llm
from backend.chat.query_validation import meaningful, validate_llm_entities
from backend.chat.service import ChatService
from backend.chat.store import ChatStore
from backend.services import data_service
from backend.services.chat_llm_settings import invalidate as invalidate_llm


OLLAMA = os.getenv("ALBION_CHAT_LLM_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
MODELS = ["qwen3:14b", "qwen3:8b", "yandexgpt5-lite:8b"]
EMBEDDING_MODELS = ["bge-m3:latest", "embeddinggemma:300m"]


# --------------------------------------------------------------- corpus


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("http://", "https://", "/storage/")):
            return ""
        return text
    if isinstance(value, dict):
        return " ".join(_json_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_json_text(item) for item in value)
    return ""


def collect_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    with data_service.get_connection() as conn:
        for row in conn.execute(
            """
            SELECT id, slug, title, excerpt, content FROM news
            WHERE is_published = TRUE ORDER BY published_at DESC NULLS LAST, id
            """
        ).fetchall():
            text = " ".join(part for part in row[2:6] if part)
            if text.strip():
                docs.append(
                    {
                        "label": f"news:{row[0]}:{row[1]}",
                        "kind": "news",
                        "title": row[2],
                        "text": text[:4000],
                        "query": f"Что писали в новости «{row[2]}»?",
                    }
                )

        for row in conn.execute(
            """
            SELECT id, label, description FROM home_geo_locations
            WHERE is_active = TRUE ORDER BY sort_order, id
            """
        ).fetchall():
            text = f"{row[1]}. {row[2] or ''}"
            docs.append(
                {
                    "label": f"geo_location:{row[0]}",
                    "kind": "geo",
                    "title": row[1],
                    "text": text,
                    "query": f"Расскажи про {row[1]}",
                }
            )

        for row in conn.execute(
            """
            SELECT id, title, description FROM home_geo_attractions
            WHERE is_active = TRUE ORDER BY sort_order, id
            """
        ).fetchall():
            docs.append(
                {
                    "label": f"geo_attraction:{row[0]}",
                    "kind": "geo",
                    "title": row[1],
                    "text": f"{row[1]}. {row[2] or ''}",
                    "query": f"Что интересного в {row[1]}?",
                }
            )

        for table, kind in (
            ("about_activity_items", "about"),
            ("about_production_items", "about"),
        ):
            for row in conn.execute(
                f"SELECT id, title, body FROM {table} ORDER BY sort_order, id"
            ).fetchall():
                docs.append(
                    {
                        "label": f"{kind}:{table}:{row[0]}",
                        "kind": "about",
                        "title": row[1],
                        "text": f"{row[1]}. {row[2] or ''}",
                        "query": f"Что входит в «{row[1]}»?",
                    }
                )

        for row in conn.execute(
            "SELECT id, name, address, schedule FROM contact_offices ORDER BY sort_order, id"
        ).fetchall():
            docs.append(
                {
                    "label": f"contact_office:{row[0]}",
                    "kind": "contacts",
                    "title": row[1],
                    "text": f"{row[1]}. {row[2] or ''}. {row[3] or ''}",
                    "query": f"Какой адрес и режим работы у офиса {row[1]}?",
                }
            )

        for row in conn.execute(
            "SELECT id, title, content FROM info_tabs WHERE is_active = TRUE ORDER BY sort_order, id"
        ).fetchall():
            if row[2] and row[2].strip():
                docs.append(
                    {
                        "label": f"info_tab:{row[0]}",
                        "kind": "info",
                        "title": row[1],
                        "text": f"{row[1]}. {row[2]}",
                        "query": f"Что указано в разделе «{row[1]}»?",
                    }
                )

        for row in conn.execute(
            "SELECT id, page_id, block_key, title, body, content FROM page_blocks WHERE is_active = TRUE ORDER BY page_id, sort_order, id"
        ).fetchall():
            text = " ".join(
                part
                for part in (row[3], row[4], _json_text(row[5]))
                if part
            )
            if text.strip():
                docs.append(
                    {
                        "label": f"page_block:{row[0]}",
                        "kind": "page",
                        "title": row[3] or row[2],
                        "text": text[:4000],
                        "query": f"Что указано в разделе «{row[3] or row[2]}»?",
                    }
                )

    return docs


def balanced_queries(docs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        by_kind.setdefault(doc["kind"], []).append(doc)

    result: list[dict[str, Any]] = []
    index = 0

    while len(result) < limit:
        added = False
        for kind in ("news", "geo", "about", "contacts", "info", "page"):
            items = by_kind.get(kind) or []
            if index < len(items):
                result.append(items[index])
                added = True
                if len(result) >= limit:
                    break
        if not added:
            break
        index += 1

    return result


# --------------------------------------------------------------- embeddings


def embed(model: str, texts: list[str]) -> list[list[float]]:
    payload = {"model": model, "input": texts, "keep_alive": "30m"}

    with httpx.Client(timeout=180) as client:
        response = client.post(f"{OLLAMA}/api/embed", json=payload)
        response.raise_for_status()
        return response.json()["embeddings"]


def unload_model(model: str) -> None:
    """Free VRAM after the benchmark (keep_alive=0)."""
    try:
        with httpx.Client(timeout=20) as client:
            client.post(
                f"{OLLAMA}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0},
            )
    except Exception:  # noqa: BLE001 — best effort
        pass


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def bench_embeddings(queries: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [doc["text"] for doc in queries]
    labels = [doc["label"] for doc in queries]
    qtexts = [doc["query"] for doc in queries]
    results = {}

    for model in EMBEDDING_MODELS:
        try:
            embed(model, ["прогрев"])
        except Exception:  # noqa: BLE001
            pass

        started = time.perf_counter()
        doc_vectors = embed(model, texts)
        index_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        query_vectors = embed(model, qtexts)
        search_ms = (time.perf_counter() - started) * 1000

        hits1 = hits3 = 0
        mrr = 0.0

        for index, query_vector in enumerate(query_vectors):
            scores = [
                (cosine(query_vector, vector), label)
                for vector, label in zip(doc_vectors, labels)
            ]
            scores.sort(reverse=True)
            top = [label for _, label in scores[:3]]
            expected = labels[index]

            if top and top[0] == expected:
                hits1 += 1
            if expected in top:
                hits3 += 1
            if expected in top:
                mrr += 1 / (top.index(expected) + 1)

        count = len(queries)
        results[model] = {
            "dimensions": len(doc_vectors[0]) if doc_vectors else 0,
            "documents": count,
            "index_ms": round(index_ms, 1),
            "query_batch_ms": round(search_ms, 1),
            "query_ms": round(search_ms / count, 2),
            "hit_at_1": round(hits1 / count * 100, 1),
            "hit_at_3": round(hits3 / count * 100, 1),
            "mrr": round(mrr / count, 3),
        }
        unload_model(model)

    return results


# --------------------------------------------------------------- extraction


def extraction_cases(limit: int) -> list[dict[str, Any]]:
    cities = [
        ("Ростове", "Ростов-на-Дону"),
        ("Таганроге", "Таганрог"),
        ("Новочеркасске", "Новочеркасск"),
        ("Шахтах", "Шахты"),
        ("Батайске", "Батайск"),
        ("Волгодонске", "Волгодонск"),
        ("Новошахтинске", "Новошахтинск"),
        ("Азове", "Азов"),
    ]
    types = [
        ("щиты", "Щит"),
        ("призматроны", "Призматрон"),
        ("скроллеры", "Сити-борд"),
        ("пиллары", "Пиллар"),
        ("сити-форматы", "Сити-формат"),
        ("видеоэкраны", "Видеоэкран"),
    ]
    months = [("октябрь", 10), ("ноябрь", 11), ("декабрь", 12), ("январь", 1)]
    sizes = [("3 на 6", "6 X 3 Метр"), ("1,2 на 1,8", "1,8 X 1,2 Метр")]

    cases: list[dict[str, Any]] = []
    templates = [
        "свободные {type} {size} в {city} на {month} до {price} рублей",
        "покажи {limit} самых дешевых {type} в {city}",
        "{type} {size} в {city} с загрузкой до {load}%",
        "{type} в {city} на {month1} и {month2}",
        "{type} на {address}",
    ]
    addresses = ["Ленина 1", "Текучева 298/96", "Стадионная", "Нагибина 127"]

    for index in range(limit):
        template = templates[index % len(templates)]
        city_in, city = cities[index % len(cities)]
        type_in, media_type = types[index % len(types)]
        month_in, month = months[index % len(months)]
        size_in, size = sizes[index % len(sizes)]
        price = 15000 + (index % 5) * 5000
        limit = 3 + index % 8
        load = 20 + (index % 5) * 10
        month2_in, month2 = months[(index + 1) % len(months)]
        address = addresses[index % len(addresses)]

        if template == templates[0]:
            query = template.format(
                type=type_in, size=size_in, city=city_in,
                month=month_in, price=price,
            )
            expected = {
                "city": city,
                "media_type": media_type,
                "size": size,
                "month": month,
                "availability": "FREE",
                "max_price": price,
            }
        elif template == templates[1]:
            query = template.format(limit=limit, type=type_in, city=city_in)
            expected = {
                "city": city,
                "media_type": media_type,
                "limit": limit,
                "sort_by": "price_asc",
            }
        elif template == templates[2]:
            query = template.format(
                type=type_in, size=size_in, city=city_in, load=load
            )
            expected = {
                "city": city,
                "media_type": media_type,
                "size": size,
                "max_load": load,
            }
        elif template == templates[3]:
            query = template.format(
                type=type_in, city=city_in,
                month1=month_in, month2=month2_in,
            )
            expected = {
                "city": city,
                "media_type": media_type,
                "months": sorted({month, month2}),
            }
        else:
            query = template.format(type=type_in, address=address)
            expected = {"media_type": media_type, "address": address}

        cases.append({"query": query, "expected": expected})

    return cases


def _field_ok(field: str, expected: Any, actual: Any) -> bool:
    if field == "address":
        return bool(actual) and str(expected).lower() in str(actual).lower()
    if field in {"city", "media_type"}:
        return (
            actual is not None
            and str(expected).casefold().replace("ё", "е")
            == str(actual).casefold().replace("ё", "е")
        )
    if field == "size":
        return str(expected) == str(actual)
    if field == "months":
        return sorted(actual or []) == sorted(expected)
    return actual == expected


def bench_models(limit: int) -> dict[str, Any]:
    cases = extraction_cases(limit)
    os.environ["ALBION_CHAT_LLM_ENABLED"] = "true"
    os.environ["ALBION_CHAT_LLM_PROVIDER"] = "ollama"
    os.environ["ALBION_CHAT_LLM_BASE_URL"] = OLLAMA
    os.environ["ALBION_CHAT_LLM_TIMEOUT"] = "60"
    os.environ["ALBION_CHAT_LLM_ANSWER_TIMEOUT"] = "60"
    os.environ["ALBION_CHAT_LLM_KEEP_ALIVE"] = "30m"
    invalidate_llm()

    class _NoBridge:
        repository = None

    service = ChatService(bridge=_NoBridge(), store=ChatStore())
    results: dict[str, Any] = {}

    for model in MODELS:
        os.environ["ALBION_CHAT_LLM_MODEL"] = model
        invalidate_llm()

        # Warm-up: load the model once, outside the measured window.
        try:
            llm.extract("прогрев")
        except Exception:  # noqa: BLE001
            pass

        latencies = []
        json_ok = 0
        pipeline_ok = 0
        field_total = 0
        field_hits = 0
        field_stats: dict[str, list[int]] = {}

        for case in cases:
            started = time.perf_counter()
            result = llm.extract(case["query"])
            latencies.append((time.perf_counter() - started) * 1000)

            raw = result.values or {}
            if raw:
                json_ok += 1

            clean, _warnings = validate_llm_entities(
                raw, service.dictionary
            )
            query = (
                service._query_from_llm(case["query"], clean)
                if meaningful(clean)
                else None
            )

            if query is not None:
                pipeline_ok += 1

            values = (
                {
                    "city": query.city,
                    "media_type": query.media_type,
                    "size": query.size,
                    "month": query.month,
                    "months": query.months,
                    "availability": query.availability,
                    "max_price": query.max_price,
                    "max_load": query.max_load,
                    "sort_by": query.sort_by,
                    "limit": query.limit,
                    "address": query.address,
                }
                if query is not None
                else {}
            )

            for field, expected in case["expected"].items():
                actual = values.get(field)
                ok = _field_ok(field, expected, actual)
                field_total += 1
                field_hits += int(ok)
                stats = field_stats.setdefault(field, [0, 0])
                stats[0] += int(ok)
                stats[1] += 1

        latencies.sort()
        results[model] = {
            "queries": len(cases),
            "json_ok": json_ok,
            "json_ok_pct": round(json_ok / len(cases) * 100, 1),
            "pipeline_ok_pct": round(pipeline_ok / len(cases) * 100, 1),
            "field_accuracy_pct": round(field_hits / field_total * 100, 1)
            if field_total
            else 0,
            "fields": {
                field: round(hits / total * 100, 1)
                for field, (hits, total) in sorted(field_stats.items())
            },
            "median_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 1),
        }
        unload_model(model)

    return results


# --------------------------------------------------------------- answers


def bench_answers() -> dict[str, Any]:
    from engine.query.query import SearchQuery

    items = [
        {
            "type": "Щит", "city": "Ростов-на-Дону", "address": "Ленина пр-кт 1",
            "side": "A", "size": "6 X 3 Метр", "price": 15400,
            "status": "SOLD", "monthly_statuses": {"10": "SOLD", "11": "FREE"},
            "month_texts": {"11": "Свободно"},
        },
        {
            "type": "Щит", "city": "Ростов-на-Дону", "address": "Текучева ул. 298/96",
            "side": "A(2)", "size": "6 X 3 Метр", "price": 18000,
            "status": "FREE", "monthly_statuses": {"10": "FREE", "11": "FREE"},
            "month_texts": {"11": "Свободно"},
        },
        {
            "type": "Щит", "city": "Ростов-на-Дону", "address": "Стадионная ул.",
            "side": "A1", "size": "6 X 3 Метр", "price": 19600,
            "status": "FREE", "monthly_statuses": {"10": "FREE", "11": "FREE"},
            "month_texts": {"11": "Свободно"},
        },
    ]
    query = SearchQuery(city="Ростов-на-Дону", media_type="Щит", month=11)

    os.environ["ALBION_CHAT_LLM_ENABLED"] = "true"
    os.environ["ALBION_CHAT_LLM_ANSWERS"] = "true"
    os.environ["ALBION_CHAT_LLM_PROVIDER"] = "ollama"
    os.environ["ALBION_CHAT_LLM_BASE_URL"] = OLLAMA
    os.environ["ALBION_CHAT_LLM_ANSWER_TIMEOUT"] = "60"
    os.environ["ALBION_CHAT_LLM_KEEP_ALIVE"] = "30m"
    invalidate_llm()

    results = {}

    for model in MODELS:
        os.environ["ALBION_CHAT_LLM_MODEL"] = model
        invalidate_llm()
        try:
            llm.answer("прогрев", query, items, total=3)
        except Exception:  # noqa: BLE001
            pass

        latencies = []
        factual = 0
        runs = 5

        for _ in range(runs):
            started = time.perf_counter()
            text = llm.answer(
                "Какие свободные щиты 6 на 3 есть в Ростове на ноябрь?",
                query,
                items,
                total=3,
            )
            latencies.append((time.perf_counter() - started) * 1000)
            low = (text or "").lower().replace("ё", "е")
            low = low.replace("стадионной", "стадионная").replace(
                "текучевой", "текучева"
            )
            price_ok = "18 000" in low or "18000" in low
            if "текучева" in low and "стадионная" in low and price_ok:
                factual += 1

        latencies.sort()
        results[model] = {
            "runs": runs,
            "fact_coverage_pct": round(factual / runs * 100, 1),
            "median_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 1),
        }
        unload_model(model)

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-limit", type=int, default=50)
    parser.add_argument("--embed-limit", type=int, default=50)
    parser.add_argument(
        "--mode",
        choices=["all", "embeddings", "extract", "answers"],
        default="all",
    )
    args = parser.parse_args()

    output: dict[str, Any] = {}

    if args.mode in {"all", "embeddings"}:
        docs = collect_documents()
        queries = balanced_queries(docs, args.embed_limit)
        output["embedding_queries"] = len(queries)
        output["documents"] = len(docs)
        output["embeddings"] = bench_embeddings(queries)

    if args.mode in {"all", "extract"}:
        output["extraction"] = bench_models(args.extract_limit)

    if args.mode in {"all", "answers"}:
        output["answers"] = bench_answers()

    Path("tmp").mkdir(exist_ok=True)
    suffix = "" if args.mode == "all" else f"_{args.mode}"
    path = Path(f"tmp/bench_chat_models{suffix}.json")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
