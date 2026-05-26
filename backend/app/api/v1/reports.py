from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.schemas.report import ReportsList, ReportReviewUpdate
from app.services import report_service, storage_service
from app.core.database import get_db
from app.api.dependencies import get_current_user, require_admin, ensure_report_access
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/get_reports_by_login", response_model=ReportsList)
async def get_id_reports(
    login: str = Query(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    ):
    try:
        reports = await report_service.get_reports_by_login(db, login)
        return ReportsList(reports=reports)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error getting reports by login")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/my_reports", response_model=ReportsList)
async def get_my_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        reports = await report_service.get_reports_by_user_id(db, current_user.id)
        return ReportsList(reports=reports)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error getting user reports")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    
@router.post("/{id_report}/add_review")
async def add_review(
    id_report: str,
    review: ReportReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    try:
        report = await report_service.get_report_by_id(db, id_report)
        ensure_report_access(current_user,report)
        await report_service.add_review(db, review, id_report)

        return {"message": "Review added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error adding review")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# View HTML report
@router.get("/{id_report}/view_html")
async def get_html_report(
    id_report: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        report = await report_service.get_report_by_id(db, id_report)
        ensure_report_access(current_user, report)

        if not report.html_object_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= "HTML report not found")

        html_bytes = await storage_service.get_object_bytes(report.html_object_key)

        return Response(
            content=html_bytes,
            media_type="text/html; charset=utf-8",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error viewing HTML report")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# Download PDF report(presigned url) - temporarily not used
@router.get("/{id_report}/pdf-url")
async def get_pdf_report_url(
    id_report: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        report = await report_service.get_report_by_id(db, id_report)
        ensure_report_access(current_user, report)

        if not report.pdf_object_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF report not found")
        
        url = await storage_service.get_presigned_url(report.pdf_object_key)
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error getting PDF URL")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{id_report}/pdf")
async def download_pdf_report(
    id_report: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await report_service.get_report_by_id(db, id_report)
        ensure_report_access(current_user, report)

        if not report.pdf_object_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF report not found",
            )
        
        pdf_bytes = await storage_service.get_object_bytes(report.pdf_object_key)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report-{id_report}.pdf"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error downloading PDF report")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/{id_report}/status")
async def get_report_status(
    id_report: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        report = await report_service.get_report_by_id(db, id_report)
        ensure_report_access(current_user, report)

        return {
            "id_report": report.id_report,
            "status": report.status,
            "error_message": report.error_message,
            "html_ready": bool(report.html_object_key),
            "pdf_ready": bool(report.pdf_object_key),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error getting report status")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")