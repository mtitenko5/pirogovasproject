from functools import wraps
from typing import Any, Dict, Optional
import asyncio
import json
import logging
import os
import re
import time

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency guard
    def load_dotenv(*args, **kwargs):
        return None

try:
    from app.core.config import get_settings
except ImportError:  # pragma: no cover - allows standalone module checks
    get_settings = None


load_dotenv()

settings = get_settings() if get_settings is not None else None
logger = logging.getLogger(__name__)


def _setting(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read setting from app config first, then from environment."""
    if settings is not None and hasattr(settings, name):
        value = getattr(settings, name)
        if value is not None:
            return value
    return os.getenv(name, default)


VLLM_BASE_URL = _setting("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_API_KEY = _setting("VLLM_API_KEY", "token-abc123")
VLLM_MODEL = _setting("VLLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

GUIDELINES_FOR_LLM_TOP_K = 4
MAX_GUIDELINE_CHARS = 900


def track_node_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] Выполнено за {elapsed:.3f} сек.")
        return result

    return wrapper


def clean_context_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_GUIDELINE_CHARS:
        text = text[:MAX_GUIDELINE_CHARS] + "..."
    return text


@track_node_time
def fuse_context(state: Dict[str, Any]) -> Dict[str, Any]:
    blocks = []
    guidelines = state.get("retrieved_guidelines", [])
    guidelines = sorted(
        guidelines,
        key=lambda item: item.get("final_score", item.get("score", 0.0)),
        reverse=True,
    )[:GUIDELINES_FOR_LLM_TOP_K]

    for i, item in enumerate(guidelines, start=1):
        score = item.get("score", item.get("final_score", 0.0))
        text = clean_context_text(item["text"])

        blocks.append(
            f"[GUIDELINE {i}]\n"
            f"Источник: {item['source']}\n"
            f"Chunk: {item['chunk_id']}\n"
            f"Score: {score:.4f}\n"
            f"Текст: {text}"
        )

    fused_context = (
        f"Жалобы:\n{state.get('query', '')}\n\n"
        f"Анамнез:\n{state.get('patient_history', '')}\n\n"
        f"Контекст из гайдлайнов:\n"
        + ("\n\n".join(blocks) if blocks else "Ничего не найдено")
    )

    return {
        **state,
        "fused_context": fused_context,
    }


def format_patient_data(patient_data: Dict[str, Any]) -> str:
    if not patient_data:
        return "Данные пациента не переданы."
    return json.dumps(patient_data, ensure_ascii=False, indent=2)


@track_node_time
def build_prompt(state: Dict[str, Any]) -> Dict[str, Any]:
    patient_data_text = format_patient_data(state.get("patient_data", {}))
    prompt = f"""
Вы — врач-кардиохирург, эксперт в области кардиологии и сосудистой хирургии с 50-летним опытом. Ваша специализация: анализ КТ-ангиографии аорты, оценка аневризм, диссекций и стенозирующих поражений.
Сформируйте заключение врача-кардиохирурга, основываясь на данных измерений КТ аорты
Справочные данные и клинические рекомендации, a так же жалобы и анамнез:
{state.get("fused_context", "")}

Результаты КТ (структурированные данные):
{patient_data_text}

<rules>
1. Анализируйте данные ТОЛЬКО на основе предоставленных материалов. Не используйте внешние медицинские базы и не домысливайте значения.Если данных недостаточно, всё равно сохраните раздел и явно напишите, чего не хватает.
2. Если в данных или контексте отсутствует информация для вывода по конкретному параметру, явно укажите: "Недостаточно данных для оценки [параметр]". Не делайте предположений.
3. Сопоставляйте измерения из JSON с референсными значениями из контекста. Указывайте единицы измерения и нормативные диапазоны.
4. Используйте строгую медицинскую терминологию и только медицинские нормы, пороги, показания, противопоказания и тактику.
<output_format>
Верните ответ строго в следующей структуре. Не добавляйте вводные/заключительные фразы вне схемы:
[Заключение] Предварительный диагноз/статус. Рекомендации по тактике (наблюдение, КТ-контроль через Х мес., консультация, хирургическое/эндоваскулярное лечение).
</output_format>
""".strip()

    return {
        **state,
        "final_prompt": prompt,
    }


@track_node_time
def call_local_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    retrieved = state.get("retrieved_guidelines", [])
    if not retrieved:
        return {
            **state,
            "raw_llm_output": "Релевантные клинические рекомендации не найдены. Недостаточно данных для анализа.",
        }

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=VLLM_MODEL,
        openai_api_base=VLLM_BASE_URL,
        openai_api_key=VLLM_API_KEY,
        temperature=0.5,
        max_tokens=8000,
    )

    response = llm.invoke(state.get("final_prompt", ""))
    answer = response.content if hasattr(response, "content") else str(response)

    return {
        **state,
        "raw_llm_output": answer,
    }


async def process_llm_request(
    patient_data: dict,
    medical_text: str,
    guideline_paths: Optional[list[str]] = None,
) -> tuple[dict, dict]:
    """Run the ML/RAG pipeline from an async service layer."""
    if not guideline_paths:
        gp = getattr(settings, "GUIDELINE_PATHS", None) if settings is not None else None
        guideline_paths = [gp] if gp and isinstance(gp, str) else (gp or [])

    ml_args = {
        "query": medical_text.strip(),
        "patient_history": medical_text.strip(),
        "patient_data": patient_data,
        "guideline_paths": guideline_paths,
    }

    try:
        # Import here to avoid circular import:
        # ml_engine imports build_prompt/call_local_llm/fuse_context from this module.
        from app.services.ml_engine import generate_medical_report

        llm_response = await asyncio.to_thread(generate_medical_report, **ml_args)
    except Exception as e:
        logger.error("LLM/RAG error in process_llm_request: %s", e, exc_info=True)
        raise

    trace_data = {
        "model": VLLM_MODEL,
        "input_keys": list(ml_args.keys()),
    }
    return llm_response, trace_data

def get_structured_answer(llm_response) -> Dict[str, str]:
    raw_report = llm_response.get("report", "")
    if not raw_report:
        return {"diagnosis": "", "clinical_recommendations": ""}

    #Вырезаем только блок [Заключение]
    match = re.search(r'\[Заключение\]\s*(.*?)(?=\[|$)', raw_report, re.DOTALL | re.IGNORECASE)
    conclusion_block = match.group(1).strip() if match else raw_report.strip()

    #Убираем служебный заголовок диагноза
    conclusion_block = re.sub(r'Предварительный\s+диагноз[/\\]статус:\s*', '', conclusion_block, flags=re.IGNORECASE)

    #Разделяем диагноз и рекомендации по началу нумерованного списка или маркеру
    rec_start = re.search(r'\n\s*\d+\.\s', conclusion_block)
    if not rec_start:
        # Try to find "Рекомендации по тактике:" marker
        rec_start = re.search(r'Рекомендации\s+по\s+тактике:\s*', conclusion_block, flags=re.IGNORECASE)

    if rec_start:
        diagnosis = conclusion_block[:rec_start.start()].strip()
        recommendations = conclusion_block[rec_start.start():].strip()
        # Remove the leading "Рекомендации по тактике:" marker from recommendations only
        recommendations = re.sub(r'^Рекомендации\s+по\s+тактике:\s*', '', recommendations, flags=re.IGNORECASE)
    else:
        diagnosis = conclusion_block
        recommendations = ""

    #Удаляем дисклеймер в конце
    disclaimer = r'(?:^|\n)Заключение\s+носит\s+информационно[ -]аналитический.*?(?:врачом|обследования)\.?'
    diagnosis = re.sub(disclaimer, '', diagnosis, flags=re.IGNORECASE | re.DOTALL).strip()
    recommendations = re.sub(disclaimer, '', recommendations, flags=re.IGNORECASE | re.DOTALL).strip()

    #Удаляем ссылки на литературу
    ref_pattern = r'\[\s*\d+(?:\s*[,\-\s]\s*\d+)*\s*\]'
    diagnosis = re.sub(ref_pattern, '', diagnosis)
    recommendations = re.sub(ref_pattern, '', recommendations)

    #Нормализация пробелов
    diagnosis = re.sub(r'\s+', ' ', diagnosis).strip()
    recommendations = re.sub(r'\n\s*\n', '\n', recommendations).strip()

    return {
        "diagnosis": diagnosis, 
        "clinical_recommendations": recommendations
        }
