from functools import wraps
from typing import Any, Dict, Optional, TypedDict, List
import logging
import threading
import time
import traceback
import os
import pickle
import numpy as np

from .bm25_index import build_bm25_corpus, _tokenize_bm25, build_bm25_index
from .chunker import build_chunks
from .embedder import embed_texts
from .graph_builder import build_knowledge_graph, load_graph_from_disk, save_graph_to_disk
from .vector_store import build_cluster_indexes, build_faiss_index, load_kb_from_disk, save_kb_to_disk

class VersionedKB(TypedDict):
    versions: Dict[str, Dict[str, Any]]
    active_version: Optional[str]
    locks: Dict[str, threading.Lock]

KB_CACHE: Dict[str, VersionedKB] = {}

#KB_CACHE: Dict[str, Dict[str, Any]] = {}
KB_CACHE_LOCKS: Dict[str, threading.Lock] = {}
KB_CACHE_LOCK = threading.Lock()

logger = logging.getLogger(__name__)

def ensure_cluster_bm25_indexes(kb: Dict[str, Any], use_bm25: bool = True) -> Dict[str, Any]:
    if not use_bm25:
        return kb

    cluster_indexes = kb.get("cluster_indexes", {})

    for cluster_name, cluster_kb in cluster_indexes.items():
        bm25_index = cluster_kb.get("bm25_index")

        if bm25_index is not None and hasattr(bm25_index, "get_scores"):
            continue

        cluster_chunks = cluster_kb.get("chunks", [])
        cluster_texts = [chunk["text"] for chunk in cluster_chunks]

        if cluster_texts:
            cluster_corpus = build_bm25_corpus(cluster_texts)
            cluster_kb["bm25_corpus"] = cluster_corpus
            cluster_kb["bm25_index"] = build_bm25_index(cluster_corpus)

    return kb

def track_node_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] Выполнено за {elapsed:.3f} сек.")
        return result

    return wrapper


@track_node_time
def ingest_request(state: Dict[str, Any]) -> Dict[str, Any]:
    errors = list(state.get("errors", []))
    warnings = list(state.get("warnings", []))

    if not state.get("query", "").strip():
        errors.append("Не передан query")

    if not state.get("guideline_paths"):
        errors.append("Не переданы пути к гайдлайнам")

    return {
        **state,
        "errors": errors,
        "warnings": warnings,
    }


def load_pdf_documents(folder_path: str):
    from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader

    pdf_loader = DirectoryLoader(
        folder_path,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
    )
    return pdf_loader.load()


def build_kb(folder_path: str, use_bm25: bool = True) -> Dict[str, Any]:
    docs = load_pdf_documents(folder_path)
    chunks = build_chunks(docs)
    texts = [chunk["text"] for chunk in chunks]

    #Считаем эмбеддинги ОДИН раз для всех чанков
    embeddings = embed_texts(texts) if texts else np.empty((0, 0), dtype=np.float32)
    text_to_emb = {t: e for t, e in zip(texts, embeddings)}
    faiss_index, dim = build_faiss_index(embeddings)
    cluster_indexes = build_cluster_indexes(chunks, text_to_emb=text_to_emb)

    graph = build_knowledge_graph(chunks)

    kb: Dict[str, Any] = {
        "docs": docs,
        "chunks": chunks,
        "faiss_index": faiss_index,
        "dim": dim,
        "knowledge_graph": graph,
        "cluster_indexes": cluster_indexes,
    }

    if use_bm25 and texts:
        corpus = build_bm25_corpus(texts)
        kb["bm25_corpus"] = corpus
        kb["bm25_index"] = build_bm25_index(corpus)

    return kb


def _get_or_create_lock(docs_path: str) -> threading.Lock:
    """Get or create a lock for a specific docs_path."""
    with KB_CACHE_LOCK:
        if docs_path not in KB_CACHE_LOCKS:
            KB_CACHE_LOCKS[docs_path] = threading.Lock()
        return KB_CACHE_LOCKS[docs_path]


def _initialize_kb_sync(docs_path: str, use_bm25: bool) -> Dict[str, Any]:
    kb = load_kb_from_disk(docs_path, use_bm25=use_bm25)

    if kb is None:
        print("KB cache not found. Building from scratch...")
        kb = build_kb(docs_path, use_bm25=use_bm25)
        save_kb_to_disk(docs_path, kb, use_bm25=use_bm25)

        if kb.get("knowledge_graph") is not None:
            save_graph_to_disk(docs_path, kb["knowledge_graph"])
    else:
        print("KB loaded from disk cache.")
        graph = load_graph_from_disk(docs_path)
        if graph is None:
            print("Graph cache not found. Building graph from chunks...")
            graph = build_knowledge_graph(kb["chunks"])
            save_graph_to_disk(docs_path, graph)

        kb["knowledge_graph"] = graph

    kb = ensure_cluster_bm25_indexes(kb, use_bm25=use_bm25)

    return kb


@track_node_time
def initialize_kb(state: Dict[str, Any]) -> Dict[str, Any]:
    warnings = list(state.get("warnings", []))
    errors = list(state.get("errors", []))
    paths = state.get("guideline_paths", [])

    if not paths:
        return {
            **state,
            "errors": errors + ["Не переданы пути к гайдлайнам"],
            "warnings": warnings,
        }

    docs_path = paths[0]
    use_bm25 = True

    try:
        # Get or create lock for this specific docs_path
        lock = _get_or_create_lock(docs_path)

        # Acquire lock for this specific docs_path
        with lock:
            if docs_path not in KB_CACHE:
                # Double-check after acquiring lock
                kb = _initialize_kb_sync(docs_path, use_bm25)
                KB_CACHE[docs_path] = kb
            kb = KB_CACHE[docs_path]

        if not kb.get("chunks"):
            warnings.append("После разбиения документов не получено ни одного чанка")

        if "knowledge_graph" not in kb:
            warnings.append("Граф знаний не был построен")

        return {
            **state,
            "chunks_count": len(kb.get("chunks", [])),
            "warnings": warnings,
            "errors": errors,
        }

    except Exception as exc:
        logger.exception("Не удалось инициализировать KB для %s", docs_path)
        tb_text = traceback.format_exc()
        return {
            **state,
            "warnings": warnings + [f"Не удалось инициализировать KB: {exc}\n\nTraceback:\n{tb_text}"],
            "errors": errors,
            "chunks_count": 0,
        }
        
def incremental_add_to_kb(docs_path: str, new_docs: List[Any], use_bm25: bool = True) -> Dict[str, Any]:
    lock = _get_or_create_lock(docs_path)
    with lock:
        kb = KB_CACHE.get(docs_path)
        if kb is None:
            kb = load_kb_from_disk(docs_path, use_bm25=use_bm25)
            if kb is None:
                return build_kb(docs_path, use_bm25=use_bm25)

        new_chunks = build_chunks(new_docs)
        if not new_chunks:
            return kb

        new_texts = [c["text"] for c in new_chunks]
        new_embeddings = embed_texts(new_texts)

        if new_embeddings.size > 0:
            kb["faiss_index"].add(new_embeddings)

        if use_bm25 and new_texts:
            if "bm25_corpus" not in kb:
                kb["bm25_corpus"] = []
            new_tokens = [_tokenize_bm25(t) for t in new_texts]
            kb["bm25_corpus"].extend(new_tokens)
            kb["bm25_index"] = build_bm25_index(kb["bm25_corpus"])

        #Мержим граф знаний
        if "knowledge_graph" in kb:
            new_graph = build_knowledge_graph(new_chunks)
            kb["knowledge_graph"].update(new_graph)

        #обновляем кластеры
        cluster_indexes = kb.get("cluster_indexes", {})
        cluster_new_tokens = {}
        for chunk, emb in zip(new_chunks, new_embeddings):
            for cluster_name in chunk.get("clusters", ["general"]):
                cl = cluster_indexes.setdefault(cluster_name, {
                    "chunks": [],
                    "faiss_index": None,
                    "dim": kb.get("dim", 0),
                    "bm25_corpus": [],
                    "bm25_index": None,
                })
                cl["chunks"].append(chunk)

                # FAISS кластера
                if cl["faiss_index"] is None:
                    cl["faiss_index"], _ = build_faiss_index(np.array([emb]))
                else:
                    cl["faiss_index"].add(np.array([emb]))

                # Собираем токены BM25 пачкой, чтобы не пересобирать индекс в цикле
                if use_bm25:
                    cluster_new_tokens.setdefault(cluster_name, []).append(_tokenize_bm25(chunk["text"]))

        if use_bm25 and cluster_new_tokens:
            for cname, new_toks in cluster_new_tokens.items():
                cluster_indexes[cname]["bm25_corpus"].extend(new_toks)
                cluster_indexes[cname]["bm25_index"] = build_bm25_index(cluster_indexes[cname]["bm25_corpus"])

        kb["chunks"].extend(new_chunks)
        kb["cluster_indexes"] = cluster_indexes
        if "docs" in kb:
            kb["docs"].extend(new_docs)

        save_kb_to_disk(docs_path, kb, use_bm25=use_bm25)
        KB_CACHE[docs_path] = kb
        return kb
