import asyncio
from datetime import datetime, timezone
import logging
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine
from app.core.enum.call_type import CallStatus
from app.core.enum.report_status import ReportStatus
from app.models.llm_calls import LLMCall
from app.models.report import Report
from app.services import llm_service, report_service
from app.services.llm_judge_runner import run_llm_judge_for_report

from app.models.report_templates import ReportTemplate

logger = logging.getLogger(__name__)

@celery_app.task(name="reports.generate_report", bind=True)
def generate_report_task(self, report_id: int, llm_call_id: int, enable_llm_judge: bool = False) -> dict:
    async def runner():
        try:
            return await _generate_report(
                report_id,
                llm_call_id,
                self.request.id,
                enable_llm_judge,
            )
        finally:
            await engine.dispose()

    return asyncio.run(runner())

async def _generate_report(report_id: int,
                           llm_call_id: int,
                           task_id: str,
                           enable_llm_judge: bool = False,
) -> dict:
    async with AsyncSessionLocal() as db:
        report = await _get_report(db, report_id)
        llm_call = await _get_llm_call(db, llm_call_id)

        try:
            report.status = ReportStatus.PROCESSING
            report.generation_started_at = datetime.now(timezone.utc)

            llm_call.status = CallStatus.PROCESSING
            llm_call.started_at = datetime.now(timezone.utc)

            await db.commit()

            llm_response, trace_data = await llm_service.process_llm_request(
                patient_data=report.measurements,
                medical_text=report.meta.get("anamnesis", ""),
                report_id=report.id_report,
            )

            trace_data.update({
                "warnings": llm_response.get("warnings", []),
                "errors": llm_response.get("errors", []),
                "celery_task_id": task_id,
            })

            has_errors = bool(trace_data.get("errors"))

            report.llm_response = llm_response.get("report")
            report.meta = {
                **(report.meta or {}),
                "guideline_sources": llm_response.get("guideline_sources", []),
            }

            llm_call.output_json = llm_response
            llm_call.trace_json = trace_data
            llm_call.status = CallStatus.FAILED if has_errors else CallStatus.COMPLETED
            llm_call.completed_at = datetime.now(timezone.utc)

            if has_errors:
                report.status = ReportStatus.FAILED
                report.error_message = "; ".join(map(str, trace_data.get("errors", [])))
            else:
                await report_service.render_and_store_report_files(db, report)
                report.status = ReportStatus.COMPLETED
                report.error_message = None
            
            report.generation_completed_at = datetime.now(timezone.utc)

            await db.commit()

            if enable_llm_judge and report.status == ReportStatus.COMPLETED:
                try:
                    await run_llm_judge_for_report(report.id_report, report.user_id)
                except Exception:
                    logger.exception("LLM judge failed for report %s", report.id_report)
            return {
                "report_id": report.id,
                "id_report": report.id_report,
                "status": report.status.value,
            }
        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            report.generation_completed_at = datetime.now(timezone.utc)
            
            llm_call.status = CallStatus.FAILED
            llm_call.error_message = str(e)
            llm_call.completed_at = datetime.now(timezone.utc)

            await db.commit()
            raise

async def _get_report(db, report_id: int) -> Report:
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise ValueError(f"Report{report_id} not found")

    return report

async def _get_llm_call(db, llm_call_id: int) -> LLMCall:
    result = await db.execute(select(LLMCall).where(LLMCall.id == llm_call_id))
    llm_call = result.scalar_one_or_none()

    if not llm_call:
        raise ValueError(f"LLMCall {llm_call_id} not found")

    return llm_call
