from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.core.database import get_db
from app.schemas.admin import (
    AdminCreateUser,
    AdminUserOut,
    AdminUpdateUser,
    AdminMetricsOut,
)
from app.schemas.report_template import ReportTemplateCreate, ReportTemplateOut
from app.schemas.clinical_protocol import ClinicalProtocolOut,ClinicalProtocolListItem
from app.services import admin_service
from app.api.dependencies import require_admin
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/create_user", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: AdminCreateUser,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    try:
        user = await admin_service.create_user(db, user_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error creating user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    return user

@router.patch("/update_user/{user_id}", response_model=AdminUserOut, status_code=status.HTTP_200_OK)
async def update_user(
    user_id: int,
    user_data: AdminUpdateUser,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
    ):
    try:
        user = await admin_service.update_user(db, user_id, user_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error updating user")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    return user

@router.post("/report-templates/upload", response_model=ReportTemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_report_template(
    name: str = Form(...),
    version: str = Form(...),
    description: Optional[str] = Form(None),
    template_file: UploadFile = File(...),
    is_active: bool = Form(False),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ReportTemplateOut:
    try:
        content = (await template_file.read()).decode("utf-8")

        template_data = ReportTemplateCreate(
            name=name,
            version=version,
            description=description,
            content=content,
            is_active=is_active,
        )

        return await admin_service.create_report_template(
            db=db,
            template_data=template_data,
            user_id=admin.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error uploading report template")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# @router.post("/clinical-protocols/replace", response_model=List[ClinicalProtocolOut])
# async def replace_clinical_protocols(
#     files: List[UploadFile] = File(...),
#     admin: User = Depends(require_admin),
#     db: AsyncSession = Depends(get_db),
# ):
#     try:
#         return await admin_service.replace_clinical_protocols(
#             db=db,
#             files=files,
#             uploaded_by_user_id=admin.id,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/clinical-protocols/add", response_model=List[ClinicalProtocolOut])
async def add_clinical_protocols(
    file: UploadFile = File(..., description="PDF file"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await admin_service.add_clinical_protocols(db=db, file=file, uploaded_by_user_id=admin.id, docs_path="clinical_protocols")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error adding clinical protocols")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/clinical-protocols", response_model=List[ClinicalProtocolListItem], status_code=status.HTTP_200_OK)
async def get_all_clinical_protocols(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        result = await admin_service.get_all_clinical_protocols(db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error getting clinical protocols")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/users", response_model=List[AdminUserOut])
async def get_all_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_all_users(db)

@router.get("/report-templates", response_model=List[ReportTemplateOut])
async def get_all_report_templates(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_all_report_templates(db)

@router.get("/metrics", response_model=AdminMetricsOut)
async def get_metrics(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_admin_metrics(db)
