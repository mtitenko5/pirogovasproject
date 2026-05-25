from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from sqlalchemy import select, desc
from app.core.database import get_db
from app.schemas.admin import AdminCreateUser, AdminUserOut, AdminUpdateUser
from app.schemas.report_template import ReportTemplateCreate, ReportTemplateOut
from app.schemas.clinical_protocol import ClinicalProtocolOut
from app.services import admin_service
from app.api.dependencies import require_admin
from app.models.user import User
from app.models.clinical_protocols import ClinicalProtocol

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/create_user", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: AdminCreateUser,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    try:
        user = await admin_service.create_user(db, user_data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/clinical-protocols/add", response_model=List[ClinicalProtocolOut])
async def add_clinical_protocols(
    file: UploadFile = File(..., description="PDF file"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)):
    try:
        return await admin_service.add_clinical_protocols(db=db, file=file, uploaded_by_user_id=admin.id, docs_path="clinical_protocols")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/clinical-protocols", response_model=List[ClinicalProtocolOut], status_code=status.HTTP_200_OK)
async def get_all_clinical_protocols(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):

    stmt = select(ClinicalProtocol).order_by(desc(ClinicalProtocol.uploaded_at))
    result = await db.execute(stmt)
    return result.scalars().all()
