from functools import wraps
from typing import Any, Dict, List, Set
import re
import time
from app.core.config import get_settings
from app.core.rag.embedder import get_embedder
import numpy as np

try:
    from .bm25_index import _tokenize_bm25
    from .chunker import CLUSTER_PATTERNS
    from .embedder import embed_texts
    from .graph_builder import graph_expand_from_chunks
except ImportError:
    from bm25_index import _tokenize_bm25
    from chunker import CLUSTER_PATTERNS
    from embedder import embed_texts
    from graph_builder import graph_expand_from_chunks

settings=get_settings()

CROSS_ENCODER_MODEL_NAME = settings.CROSS_ENCODER_MODEL_NAME
EMBEDDING_MODEL_NAME=settings.EMBEDDING_MODEL_NAME
_CROSS_ENCODER = None
_MORPH = None
_EMBEDDER = None

SYMPTOM_TOP_K = 4
JSON_CANDIDATES_TOP_K = 10
JSON_RESULTS_TOP_K = 5
GRAPH_EXPAND_TOP_K = 8
FINAL_GUIDELINES_TOP_K = 4

MIN_JSON_RELEVANCE_SCORE = 3.0
MIN_FINAL_RELEVANCE_SCORE = 3.0

TRANSLATION_MAP = {
    "Descending Aorta": "Нисходящая аорта",
    "Isthmus": "Перешеек аорты",
    "Arch after LSA": "Дуга аорты после отхождения левой подвключичной артерии",
    "Arch after TBC": "Дуга аорты после отхождения плечеголовного ствола",
    "Ascending Aorta befor TBC": "Восходящая аорта перед плечеголовным стволом",
    "Ascending Aorta": "Восходящая аорта",
    "max_diam_1": "Максимальные диаметры",
    "max_diam_2": "Максимальные диаметры",
    "min_diam": "Минимальный диаметр",
    "perimetr": "Периметр сосуда",
    "area": "Площадь поперечного сечения",
}

def log_step_time(step_name: str, start_time: float) -> float:
    now = time.perf_counter()
    print(f"[retrieve_graph_context] {step_name}: {now - start_time:.3f} сек.")
    return now
    
def track_node_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] Выполнено за {elapsed:.3f} сек.")
        return result

    return wrapper


def get_cross_encoder():
    global _CROSS_ENCODER
    if _CROSS_ENCODER is None:
        from sentence_transformers import CrossEncoder

        _CROSS_ENCODER = CrossEncoder(CROSS_ENCODER_MODEL_NAME, device="cpu")
    return _CROSS_ENCODER


def get_morph():
    global _MORPH
    if _MORPH is None:
        import pymorphy3
        _MORPH = pymorphy3.MorphAnalyzer()
    return _MORPH


def _normalize_text(text: str) -> Set[str]:
    words = re.findall(r"\b[а-яА-ЯёЁa-zA-Z]{3,}\b", text.lower())
    morph = get_morph()
    return {morph.parse(word)[0].normal_form for word in words}


def _flatten_patient_measurements(patient_data: Dict[str, Any]) -> List[str]:
    facts: List[str] = []

    if not isinstance(patient_data, dict):
        return facts

    for zone_key, zone_value in patient_data.items():
        zone_name = TRANSLATION_MAP.get(zone_key, zone_key)

        if isinstance(zone_value, dict):
            for metric_key, metric_value in zone_value.items():
                metric_name = TRANSLATION_MAP.get(metric_key, metric_key)

                if isinstance(metric_value, (int, float)):
                    facts.append(f"{zone_name} {metric_name} {metric_value} мм")
                elif isinstance(metric_value, list):
                    numeric_values = [str(value) for value in metric_value if isinstance(value, (int, float))]
                    if numeric_values:
                        facts.append(f"{zone_name} {metric_name} {' '.join(numeric_values)} мм")
                elif isinstance(metric_value, dict):
                    for sub_key, sub_value in metric_value.items():
                        sub_name = TRANSLATION_MAP.get(sub_key, sub_key)
                        if isinstance(sub_value, (int, float)):
                            facts.append(f"{zone_name} {metric_name} {sub_name} {sub_value} мм")
                        elif isinstance(sub_value, list):
                            numeric_values = [str(value) for value in sub_value if isinstance(value, (int, float))]
                            if numeric_values:
                                facts.append(f"{zone_name} {metric_name} {sub_name} {' '.join(numeric_values)} мм")
        elif isinstance(zone_value, (int, float)):
            facts.append(f"{zone_name} {zone_value} мм")

    return facts


def _collect_json_keywords(patient_data: Dict[str, Any]) -> Set[str]:
    keywords: Set[str] = set()

    if not isinstance(patient_data, dict):
        return keywords

    for zone_key, zone_value in patient_data.items():
        zone_name = TRANSLATION_MAP.get(zone_key, zone_key)
        keywords.update(_normalize_text(zone_name))

        if isinstance(zone_value, dict):
            for metric_key in zone_value.keys():
                metric_name = TRANSLATION_MAP.get(metric_key, metric_key)
                keywords.update(_normalize_text(metric_name))

    return keywords


def _build_json_query(patient_data: Dict[str, Any]) -> str:
    facts = _flatten_patient_measurements(patient_data)

    base_terms = (
        "норма аорты нормальный диаметр аневризма расширение "
        "порог вмешательства показания к операции риск расслоения "
        "восходящая аорта нисходящая аорта дуга аорты перешеек "
        "максимальный диаметр минимальный диаметр периметр площадь поперечного сечения "
        "мм см таблица рекомендации"
    )

    return f"{base_terms} {' '.join(facts)}".strip()


def route_query_to_clusters(
    query: str,
    patient_history: str,
    patient_data: Dict[str, Any],
) -> List[str]:
    query_parts = [query, patient_history]

    if isinstance(patient_data, dict):
        query_parts.append(_build_json_query(patient_data))

    full_query = "\n".join(query_parts).lower()
    clusters: List[str] = []

    for cluster_name, patterns in CLUSTER_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in full_query:
                clusters.append(cluster_name)
                break

    if not clusters:
        clusters.append("general")

    return clusters
    
def warmup_retriever_models() -> None:
    print("[warmup] Loading retriever runtime models...")

    # Загружаем embedding model
    embed_texts(["warmup"], is_query=True)

    # Загружаем cross-encoder
    get_cross_encoder()

    # Загружаем pymorphy3
    get_morph()

    print("[warmup] Retriever runtime models loaded.")   
    
from celery.signals import worker_process_init

@worker_process_init.connect
def warmup_worker(**kwargs):
    from app.core.rag.retriever import warmup_retriever_models
    warmup_retriever_models()


def hybrid_retrieve(query: str, kb: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
    chunks = kb.get("chunks", [])
    faiss_index = kb.get("faiss_index")

    if faiss_index is None or not chunks:
        return []

    q_emb = embed_texts([query], is_query=True)
    if q_emb.size == 0:
        return []

    k_search = min(len(chunks), max(top_k * 3, top_k))
    distances, indices = faiss_index.search(q_emb, k_search)
    vector_ranks = [int(idx) for idx in indices[0] if int(idx) >= 0]

    bm25_ranks = None
    if kb.get("bm25_index"):
        q_tokens = _tokenize_bm25(query)
        bm25_scores = kb["bm25_index"].get_scores(q_tokens)
        bm25_ranks = np.argsort(bm25_scores)[::-1]

    rrf_scores = np.zeros(len(chunks))
    k_rrf = 60.0

    def apply_rrf(ranks, target):
        for rank, idx in enumerate(ranks, start=1):
            if 0 <= int(idx) < len(target):
                target[int(idx)] += 1.0 / (k_rrf + rank)

    apply_rrf(vector_ranks, rrf_scores)
    if bm25_ranks is not None:
        apply_rrf(bm25_ranks, rrf_scores)

    candidate_indices = np.argsort(rrf_scores)[::-1][: top_k * 3]
    results: List[Dict[str, Any]] = []

    for idx in candidate_indices:
        idx = int(idx)
        if rrf_scores[idx] <= 0:
            continue
        results.append(
            {
                "source": chunks[idx]["source"],
                "chunk_id": chunks[idx]["chunk_id"],
                "text": chunks[idx]["text"],
                "index": idx,
                "score": float(rrf_scores[idx]),
            }
        )

    if results:
        pairs = [[query, result["text"]] for result in results]
        ce_scores = get_cross_encoder().predict(pairs, show_progress_bar=False)
        for i, result in enumerate(results):
            result["score"] = 0.3 * result["score"] + 0.7 * float(ce_scores[i])

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def hybrid_retrieve_from_clusters(query: str, kb: Dict[str, Any], target_clusters: List[str], top_k: int) -> List[Dict[str, Any]]:
    cluster_indexes = kb.get("cluster_indexes", {})

    if not target_clusters or "general" in target_clusters:
        return hybrid_retrieve(query, kb, top_k)

    all_results: List[Dict[str, Any]] = []

    for cluster in target_clusters:
        cluster_kb = cluster_indexes.get(cluster)
        if not cluster_kb:
            continue

        cluster_results = hybrid_retrieve(query=query, kb=cluster_kb, top_k=top_k)

        for result in cluster_results:
            result["matched_cluster"] = cluster

        all_results.extend(cluster_results)

    if not all_results:
        return hybrid_retrieve(query, kb, top_k)

    seen: Dict[Any, Dict[str, Any]] = {}
    for item in all_results:
        key = (item["source"], item["chunk_id"])
        if key not in seen or item["score"] > seen[key]["score"]:
            seen[key] = item

    results = list(seen.values())
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def _apply_json_heuristics(candidates: List[Dict[str, Any]], keywords_from_json: Set[str]) -> List[Dict[str, Any]]:
    for candidate in candidates:
        chunk_lower = candidate["text"].lower()
        chunk_normalized = _normalize_text(candidate["text"])

        matches = keywords_from_json.intersection(chunk_normalized)
        candidate["score"] += len(matches) * 0.05

        numeric_patterns = [
            r"\d{1,2}(\.\d)?\s?мм",
            r"[><=]\s?\d{1,2}",
            r"от\s\d{1,2}\sдо\s\d{1,2}",
        ]
        for pattern in numeric_patterns:
            if re.search(pattern, chunk_lower):
                candidate["score"] += 0.15

        stop_patterns = [
            "рис.",
            "рисунок",
            "вид сбоку",
            "снимок",
            "визуализация",
            "иллюстрация",
            "график",
        ]
        for stop_word in stop_patterns:
            if stop_word in chunk_lower:
                candidate["score"] -= 0.10

        reference_matches = re.findall(r"\[[\d,\s\-]+\]", chunk_lower)
        if reference_matches:
            candidate["score"] -= len(reference_matches) * 0.005

    return candidates


def merge_retrieval_results(
    vector_results: List[Dict[str, Any]],
    graph_results: List[Dict[str, Any]],
    final_top_k: int = FINAL_GUIDELINES_TOP_K,
) -> List[Dict[str, Any]]:
    merged: Dict[Any, Dict[str, Any]] = {}

    for item in vector_results:
        key = (item["source"], item["chunk_id"])
        merged[key] = {
            **item,
            "vector_score": item.get("score", 0.0),
            "graph_score": 0.0,
            "final_score": item.get("score", 0.0),
            "retrieval_type": "vector",
        }

    for item in graph_results:
        key = (item["source"], item["chunk_id"])

        if key in merged:
            merged[key]["graph_score"] = item.get("graph_score", item.get("score", 0.0))
            merged[key]["graph_path"] = item.get("graph_path", "")
            merged[key]["retrieval_type"] = "vector+graph"
            merged[key]["final_score"] = (
                0.65 * merged[key].get("vector_score", 0.0)
                + 0.35 * merged[key].get("graph_score", 0.0)
            )
        else:
            merged[key] = {
                **item,
                "vector_score": 0.0,
                "graph_score": item.get("graph_score", item.get("score", 0.0)),
                "final_score": 0.35 * item.get("score", 0.0),
                "retrieval_type": "graph",
            }

    results = list(merged.values())
    results.sort(key=lambda item: item["final_score"], reverse=True)

    # Filter by MIN_FINAL_RELEVANCE_SCORE
    filtered_results = [
        result for result in results
        if result["final_score"] >= MIN_FINAL_RELEVANCE_SCORE
    ]

    return filtered_results[:final_top_k]


@track_node_time
def retrieve_graph_context(state: Dict[str, Any]) -> Dict[str, Any]:
    total_start = time.perf_counter()
    step_start = total_start

    try:
        from .kb_manager import KB_CACHE
    except ImportError:
        from kb_manager import KB_CACHE

    warnings = list(state.get("warnings", []))
    paths = state.get("guideline_paths", [])

    step_start = log_step_time("import/cache access", step_start)

    if not paths:
        return {
            **state,
            "retrieved_guidelines": [],
            "warnings": warnings + ["Не переданы пути к гайдлайнам"],
        }

    docs_path = paths[0]
    kb = KB_CACHE.get(docs_path)

    if kb is None:
        return {
            **state,
            "retrieved_guidelines": [],
            "warnings": warnings + ["KB не инициализирована"],
        }

    patient_data = state.get("patient_data", {})
    symptom_query = (
        f"{state.get('query', '')}\n"
        f"{state.get('patient_history', '')}"
    ).strip()

    target_clusters = route_query_to_clusters(
        query=state.get("query", ""),
        patient_history=state.get("patient_history", ""),
        patient_data=patient_data,
    )

    print(f"[retrieve_graph_context] target_clusters={target_clusters}")
    step_start = log_step_time("route_query_to_clusters", step_start)

    symptom_results = hybrid_retrieve_from_clusters(
        query=symptom_query,
        kb=kb,
        target_clusters=target_clusters,
        top_k=SYMPTOM_TOP_K,
    )

    step_start = log_step_time("symptom hybrid retrieve", step_start)

    json_query = ""
    keywords_from_json: Set[str] = set()

    if patient_data and isinstance(patient_data, dict):
        json_query = _build_json_query(patient_data)
        keywords_from_json = _collect_json_keywords(patient_data)

    step_start = log_step_time("build json query/keywords", step_start)

    json_candidates = (
        hybrid_retrieve_from_clusters(
            query=json_query,
            kb=kb,
            target_clusters=target_clusters,
            top_k=JSON_CANDIDATES_TOP_K,
        )
        if json_query
        else []
    )

    step_start = log_step_time("json hybrid retrieve", step_start)

    json_candidates = _apply_json_heuristics(json_candidates, keywords_from_json)

    step_start = log_step_time("json heuristics", step_start)

    graph_results = graph_expand_from_chunks(
        seed_results=symptom_results + json_candidates[:JSON_RESULTS_TOP_K],
        kb=kb,
        max_hops=2,
        max_graph_chunks=GRAPH_EXPAND_TOP_K,
    )

    step_start = log_step_time("graph expand", step_start)

    final_guidelines = merge_retrieval_results(
        vector_results=symptom_results + json_candidates[:JSON_RESULTS_TOP_K],
        graph_results=graph_results,
        final_top_k=FINAL_GUIDELINES_TOP_K,
    )

    step_start = log_step_time("merge results", step_start)
    log_step_time("TOTAL retrieve_graph_context", total_start)

    if not final_guidelines:
        warnings.append("Ретривер не нашёл релевантных фрагментов")

    return {
        **state,
        "retrieved_guidelines": final_guidelines,
        "warnings": warnings,
    }
