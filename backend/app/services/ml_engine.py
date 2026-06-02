from pathlib import Path
from typing import Any, Dict, List, TypedDict, Optional
import json
import logging
import uuid
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from app.core.rag.kb_manager import ingest_request, initialize_kb
from app.services.llm_service import build_prompt, call_local_llm, fuse_context
from app.core.rag.retriever import retrieve_graph_context

logger = logging.getLogger(__name__)

class MedGraphState(TypedDict, total=False):
    query: str
    patient_history: str
    guideline_paths: List[str]
    persist_dir: str
    patient_data: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    retrieved_guidelines: List[Dict[str, Any]]
    fused_context: str
    final_prompt: str
    raw_llm_output: str
    chunks_count: int
    #diagnosis: str
    #clinical_recommendations: str 
    
def configure_logging(level: int = logging.INFO) -> None:
    """
    Configures application logging for local script runs.

    In production/FastAPI this function can be skipped if logging is already
    configured by the application server.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

def validate_and_set_defaults(state: MedGraphState) -> MedGraphState:
    defaults = {
        "query": "Жалоб на здоровье нет",
        "patient_history": "Анамнез не предоставлен",
        "patient_data": {},
        "guideline_paths": [],
        "warnings": [],
        "errors": []
    }
    # Обновляем только отсутствующие или пустые поля
    updates = {k: v for k, v in defaults.items() if not state.get(k)}
    return updates

def build_graph():
    builder = StateGraph(MedGraphState)
    builder.add_node("validate_input", validate_and_set_defaults)
    builder.add_node("ingest_request", ingest_request)
    builder.add_node("initialize_kb", initialize_kb)
    builder.add_node("retrieve_graph_context", retrieve_graph_context)
    builder.add_node("fuse_context", fuse_context)
    builder.add_node("build_prompt", build_prompt)
    builder.add_node("call_local_llm", call_local_llm)

    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "ingest_request")             
    builder.add_edge("ingest_request", "initialize_kb")
    builder.add_edge("initialize_kb", "retrieve_graph_context")
    builder.add_edge("retrieve_graph_context", "fuse_context")
    builder.add_edge("fuse_context", "build_prompt")
    builder.add_edge("build_prompt", "call_local_llm")
    builder.add_edge("call_local_llm", END)

    return builder.compile(checkpointer=InMemorySaver())


def load_patient_data(path: str = "content/0.json") -> Dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return {}

    with open(json_path, "r", encoding="utf-8") as file:
        return json.load(file)


def export_langsmith_runs(
    project_name: str = "clinical-rag",
    limit: int = 11,
    output_path: str = "langsmith_runs.jsonl",
) -> None:
    from langsmith import Client

    client = Client()
    runs = client.list_runs(project_name=project_name, limit=limit)

    with open(output_path, "w", encoding="utf-8") as file:
        exported_count=0
        for run in runs:
            data = {
                "id": str(run.id),
                "name": run.name,
                "start_time": str(run.start_time),
                "end_time": str(run.end_time),
                "inputs": run.inputs,
                "outputs": run.outputs,
            }
            file.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
            exported_count += 1

    logger.info("LangSmith runs were exported successfully: count=%s", exported_count)
    
graph = build_graph()

def generate_medical_report(query: str, patient_history: str, patient_data: dict, guideline_paths: list[str], report_id: Optional[str] = None) -> Dict[str, Any]:
    initial_state: MedGraphState = {
        "query": query,
        "patient_history": patient_history,
        "guideline_paths": guideline_paths,
        "patient_data": patient_data,
        "thread_id": f"api-{uuid.uuid4()}",
        "warnings": [],
        "errors": [],
    }

    config = {"configurable": {"thread_id": "api-request"}, "metadata": {"report_id": report_id}}
    result = graph.invoke(initial_state, config=config)

    guideline_sources = sorted({
        item.get("source")
        for item in result.get("retrieved_guidelines", [])
        if item.get("source")
    })

    return {
        "report": result.get("raw_llm_output"),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
        "guideline_sources": guideline_sources,
    }
