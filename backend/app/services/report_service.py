from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List, Optional, Set
import asyncio
from langsmith import Client
import os
import logging
import base64

from app.models.report import Report
from app.models.user import User
from app.models.llm_calls import LLMCall
from app.models.report_templates import ReportTemplate
from app.core.enum.report_status import ReportStatus
from app.schemas.report import ReportReviewUpdate
from app.core.enum.call_type import CallType, CallStatus
from app.core.config import get_settings
from app.services import storage_service

from app.utils.pdf_generator import generate_pdf_from_html
from app.utils.html_report_generator import generate_html_report

logger = logging.getLogger(__name__)

# Track background feedback tasks to prevent them from being garbage collected
feedback_tasks: Set[asyncio.Task] = set()

async def create_queued_report(
    db: AsyncSession,
    measurements: dict,
    input_files: dict,
    meta: dict,
    user_id: int,
    judge_enabled: bool,
    template_id: Optional[int] = None,
) -> tuple[Report, LLMCall]:
    settings = get_settings()
    
    id_report = str(uuid.uuid4())
    report = Report(
        id_report=id_report,
        user_id=user_id,
        status =ReportStatus.PROCESSING,
        input_files=input_files,
        measurements=measurements,
        meta=meta,
        llm_response=None,
        judge_enabled=judge_enabled,
        judge_status="queued" if judge_enabled else None,
        template_id=template_id,
    )
    db.add(report)
    await db.flush()

    llm_call = LLMCall(
        report_id=report.id,
        user_id=user_id,
        status=CallStatus.QUEUED,
        call_type=CallType.REPORT_GENERATION,
        provider="vllm",
        model=settings.VLLM_MODEL,
        prompt=meta.get("anamnesis", ""),
        template_id=template_id,
        input_json={
            "measurements": measurements,
            "meta": meta,
        },
    )
    db.add(llm_call)

    await db.commit()
    await db.refresh(report)
    await db.refresh(llm_call)

    return report, llm_call

async def get_report_by_id(db:AsyncSession, id_report:str) -> Report:
    result = await db.execute(select(Report).where(Report.id_report == id_report))
    report = result.scalar_one_or_none()

    if not report:
        raise ValueError("Report not found")

    return report

async def get_reports_by_login(db: AsyncSession, login: str):
    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")
    
    result = await db.execute(select(Report).where(Report.user_id == user.id))
    reports = result.scalars().all()
    return reports

async def get_reports_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> List[Report]:
    result = await db.execute(select(Report).where(Report.user_id == user_id))
    result = result.scalars().all()
    return result

async def _build_ct_image_data(report: Report) -> list[dict]:
    images = []
    raw_images = (report.input_files or {}).get("ct_images", [])

    if isinstance(raw_images, dict):
        raw_images = [raw_images]

    for image in raw_images:
        object_key = image.get("object_key")
        if not object_key:
            continue

        image_bytes = await storage_service.get_object_bytes(object_key)
        content_type = image.get("content_type") or "image/jpeg"
        encoded = base64.b64encode(image_bytes).decode("ascii")

        images.append({
            "filename": image.get("filename", "КТ-снимок"),
            "src": f"data:{content_type};base64,{encoded}",
        })

    return images

async def render_and_store_report_files(
    db: AsyncSession,
    report: Report,
) -> tuple[str, str]:
    template_content = await _get_template_content(db, report.template_id)
    ct_images = await _build_ct_image_data(report)
    html_content = generate_html_report(
        report,
        template_content=template_content,
        ct_images=ct_images,
    )
    html_object_key = await storage_service.upload_text(
        text=html_content,
        prefix=f"reports/{report.id_report}/result",
        filename="report.html",
        content_type="text/html; charset=utf-8",
    )

    pdf_content = generate_pdf_from_html(html_content)
    pdf_object_key = await storage_service.upload_bytes_file(
        data=pdf_content,
        prefix=f"reports/{report.id_report}/result",
        filename="report.pdf",
        content_type="application/pdf",
    )

    report.html_object_key = html_object_key
    report.pdf_object_key = pdf_object_key

    await db.flush()

    return html_object_key, pdf_object_key
    
async def add_review(db: AsyncSession, review: ReportReviewUpdate, id_report: str):
    result = await db.execute(select(Report).where(Report.id_report == id_report))
    report = result.scalar_one_or_none()
    if not report:
        raise ValueError("Report not found")
    report.review_score = review.review_score
    report.review_text = review.review_text
    await db.commit()

    # Fire-and-forget: send feedback to LangSmith without blocking or failing the endpoint
    task = asyncio.create_task(_send_feedback_to_langsmith_wrapper(id_report, review.review_score, review.review_text))
    feedback_tasks.add(task)
    task.add_done_callback(feedback_tasks.discard)

async def _send_feedback_to_langsmith_wrapper(report_id: str, score: int, comment: str):
    """Wrapper to call LangSmith feedback in background without blocking."""
    try:
        await asyncio.to_thread(_send_feedback_to_langsmith, report_id, score, comment)
    except Exception as e:
        logger.exception(f"Failed to send feedback to LangSmith for report {report_id}: {e}")

def _send_feedback_to_langsmith(report_id: str, score: int, comment: str):
    client = Client()
    project = os.getenv("LANGSMITH_PROJECT", "clinical-rag")

    filter_string = (
        f"and("
        f"eq(metadata_key, 'report_id'), "
        f"eq(metadata_value, '{report_id}')"
        f")"
    )

    runs = client.list_runs(
        project_name=project,
        filter=filter_string,
        is_root=True,
        limit=1,
    )

    run = next(runs, None)
    if not run:
        return

    client.create_feedback(
        run_id=run.id,
        key="doctor_rating",
        score=score,
        comment=comment or "",
    )


async def _get_template_content(db: AsyncSession, template_id: Optional[int]) -> Optional[str]:
    """Возвращает content шаблона по ID или активный по умолчанию."""
    if template_id is not None:
        result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
        tpl = result.scalar_one_or_none()
        if tpl:
            return tpl.content

    #любой активный шаблон
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.is_active == True).order_by(ReportTemplate.updated_at.desc()).limit(1))
    tpl = result.scalar_one_or_none()
    return tpl.content if tpl else None
