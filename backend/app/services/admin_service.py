from fastapi import HTTPException, status, UploadFile
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.report import Report
from app.models.llm_calls import LLMCall
from app.core.enum.call_type import CallStatus

from app.models.user import User, Organization
from app.models.report_templates import ReportTemplate
from app.models.clinical_protocols import ClinicalProtocol

from app.schemas.admin import AdminCreateUser, AdminUserOut, AdminUpdateUser
from app.schemas.report_template import ReportTemplateCreate
from app.core.security import get_password_hash, verify_password
from app.core.enum.role import UserRole
from app.services import storage_service
from app.core.enum.clinical_protocol_status import ClinicalProtocolStatus

from pathlib import Path
import tempfile
from langchain_community.document_loaders import PyPDFLoader
from app.core.rag.kb_manager import incremental_add_to_kb

async def create_user(db: AsyncSession, user_data: AdminCreateUser) -> User:
    result = await db.execute(select(User).where(User.login == user_data.login))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Login is already registered"
        )
    
    organization_result = await db.execute( select(Organization).where(Organization.name == user_data.organization_name))
    organization = organization_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found"
        )
    
    hashed_password = get_password_hash(user_data.password)

    new_user = User(
        login=user_data.login,
        hashed_password=hashed_password,
        role = user_data.role,
        organization_name=user_data.organization_name,
        name=user_data.name,
        surname=user_data.surname,
        patronymic=user_data.patronymic,
        date_of_birth=user_data.date_of_birth
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def update_user(db: AsyncSession, user_id: int, user_data: AdminUpdateUser):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user_data.organization_name:
        organization_result = await db.execute( select(Organization).where(Organization.name == user_data.organization_name))
        organization = organization_result.scalar_one_or_none()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found"
            )
    
    if user_data.role == UserRole.USER and user.role == UserRole.ADMIN or user_data.is_active == False and user.role == UserRole.ADMIN:
        admins = await db.execute(select(User).where(User.role == UserRole.ADMIN))
        admins = admins.scalars().all()
        if len(admins) == 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can assign admin role"
            )
        
    update_dict = user_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)

    return user
    
async def create_report_template(
    db: AsyncSession,
    template_data: ReportTemplateCreate,
    user_id: int,
) -> ReportTemplate:
    if template_data.is_active:
        await db.execute(
            update(ReportTemplate).values(is_active=False)
        )
    
    template = ReportTemplate(
        name=template_data.name,
        version=template_data.version,
        description=template_data.description,
        content=template_data.content,
        is_active=template_data.is_active,
        created_by_user_id=user_id,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return template

# async def replace_clinical_protocols(
#     files: List[UploadFile],
#     uploaded_by_user_id: int,
#     db: AsyncSession,
# ) -> List[ClinicalProtocol]:
#     old_protocols = (await db.execute(select(ClinicalProtocol))).scalars().all()
#
#     for protocol in old_protocols:
#         if protocol.file_object_key:
#             await storage_service.delete_object(protocol.file_object_key)
#         await db.delete(protocol)
#
#
#     created_protocols = []
#
#     for file in files:
#         object_key = await storage_service.upload_file(
#             file = file,
#             prefix = "clinical_protocols/",
#         )
#
#         protocol = ClinicalProtocol(
#             title = file.filename,
#             file_object_key = object_key,
#             uploaded_by_user_id = uploaded_by_user_id,
#             status = ClinicalProtocolStatus.UPLOADED,
#         )
#
#         db.add(protocol)
#         created_protocols.append(protocol)
#
#     await db.commit()
#
#     for protocol in created_protocols:
#         await db.refresh(protocol)
#
#     return created_protocols

async def add_clinical_protocols(file: UploadFile, uploaded_by_user_id: int, db: AsyncSession, docs_path: str = "clinical_protocols") -> List[ClinicalProtocol]:
    new_docs = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} is not a PDF file"
            )
        tmp_path = Path(tmp_dir) / file.filename
        content = await file.read()
        await file.seek(0)
        tmp_path.write_bytes(content)
        loader = PyPDFLoader(str(tmp_path))
        new_docs.extend(loader.load())

    # Step 1: Upload file to storage first
    object_key = await storage_service.upload_file(file=file, prefix="clinical_protocols/")

    # Step 2: Create protocol with PENDING status
    protocol = ClinicalProtocol(
        title=file.filename,
        file_object_key=object_key,
        uploaded_by_user_id=uploaded_by_user_id,
        status=ClinicalProtocolStatus.PENDING
    )
    db.add(protocol)

    # Step 3: Commit to persist the record
    try:
        await db.commit()
        await db.refresh(protocol)
    except Exception:
        # Clean up orphaned storage object if database save fails
        try:
            await storage_service.delete_object(object_key)
        except Exception:
            pass  # Best effort cleanup
        raise

    # Step 4: Index the documents in the knowledge base
    try:
        incremental_add_to_kb(docs_path, new_docs, use_bm25=True)
        # Step 5: Update status to INDEXED after successful indexing
        protocol.status = ClinicalProtocolStatus.INDEXED
        await db.commit()
    except Exception as e:
        # Rollback: delete uploaded file and set status to FAILED
        protocol.status = ClinicalProtocolStatus.FAILED
        await db.commit()
        try:
            await storage_service.delete_object(object_key)
        except Exception:
            pass  # Best effort cleanup
        raise HTTPException(
            status_code=500,
            detail="Failed to index clinical protocol in knowledge base"
        ) from e

    return [protocol]

async def get_all_clinical_protocols(db: AsyncSession) -> List[ClinicalProtocol]:
    
    result = await db.execute(
        select(ClinicalProtocol).order_by(ClinicalProtocol.uploaded_at.desc())
    )
    return list(result.scalars().all())

async def get_all_users(db: AsyncSession) -> List[User]:
    result = await db.execute(select(User).order_by(User.id))
    return list(result.scalars().all())

async def get_all_report_templates(db: AsyncSession) -> List[ReportTemplate]:
    result = await db.execute(select(ReportTemplate).order_by(ReportTemplate.created_at.desc()))
    return list(result.scalars().all())

async def get_admin_metrics(db: AsyncSession) -> dict:
    llm_total_result = await db.execute(select(func.count(LLMCall.id)))
    llm_calls_total = llm_total_result.scalar_one()

    llm_failed_result = await db.execute(
        select(func.count(LLMCall.id)).where(LLMCall.status == CallStatus.FAILED)
    )
    llm_calls_failed = llm_failed_result.scalar_one()

    reviewed_count_result = await db.execute(
        select(func.count(Report.id)).where(Report.review_score.is_not(None))
    )
    reviewed_reports_total = reviewed_count_result.scalar_one()

    avg_review_result = await db.execute(
        select(func.avg(Report.review_score)).where(Report.review_score.is_not(None))
    )
    average_review_score = avg_review_result.scalar_one()

    llm_error_percent = 0.0
    if llm_calls_total:
        llm_error_percent = round((llm_calls_failed / llm_calls_total) * 100, 2)

    return {
        "llm_calls_total": llm_calls_total,
        "llm_calls_failed": llm_calls_failed,
        "llm_error_percent": llm_error_percent,
        "reviewed_reports_total": reviewed_reports_total,
        "average_review_score": round(float(average_review_score), 2) if average_review_score is not None else None,
    }
