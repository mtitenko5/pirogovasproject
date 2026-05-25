from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.report_templates import ReportTemplate
from app.models.clinical_protocols import ClinicalProtocol
from app.models.llm_calls import LLMCall
from app.models.user import User, Organization

from app.core.config import get_settings
from app.core.enum.role import UserRole
from app.core.enum.clinical_protocol_status import ClinicalProtocolStatus
from app.core.security import get_password_hash
from app.core.database import engine, Base, AsyncSessionLocal

import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def bootstrap_first_admin(db: AsyncSession) -> None:
    organization_exists_result = await db.execute(
        select(Organization).where(Organization.name == get_settings().FIRST_ORGANIZATION_NAME)
    )
    organization = organization_exists_result.scalar_one_or_none()

    if not organization:
        organization = Organization(
            name=get_settings().FIRST_ORGANIZATION_NAME
        )
        db.add(organization)
        await db.commit()
        await db.refresh(organization)

    users_to_create = [
    {
        "login": get_settings().FIRST_ADMIN_LOGIN,
        "password": get_settings().FIRST_ADMIN_PASSWORD,
        "role": UserRole.ADMIN,
        "name": get_settings().FIRST_ADMIN_NAME,
        "surname": get_settings().FIRST_ADMIN_SURNAME,
        "patronymic": get_settings().FIRST_ADMIN_PATRONYMIC,
        "date_of_birth": get_settings().FIRST_ADMIN_DATE_OF_BIRTH,
    },
    ]

    if get_settings().SEED_DEMO_USERS:
        users_to_create.extend(
            [
                {
                    "login": "doctor1",
                    "password": "doctor123",
                    "role": UserRole.USER,
                    "name": "Doctor",
                    "surname": "One",
                    "patronymic": "User",
                    "date_of_birth": get_settings().FIRST_ADMIN_DATE_OF_BIRTH,
                },
                {
                    "login": "doctor2",
                    "password": "doctor123",
                    "role": UserRole.USER,
                    "name": "Doctor",
                    "surname": "Two",
                    "patronymic": "User",
                    "date_of_birth": get_settings().FIRST_ADMIN_DATE_OF_BIRTH,
                },
                {
                    "login": "doctor3",
                    "password": "doctor123",
                    "role": UserRole.USER,
                    "name": "Doctor",
                    "surname": "Three",
                    "patronymic": "User",
                    "date_of_birth": get_settings().FIRST_ADMIN_DATE_OF_BIRTH,
                },
            ]
        )

    for user_data in users_to_create:
        existing_user_result = await db.execute(
            select(User).where(User.login == user_data["login"])
        )
        existing_user = existing_user_result.scalar_one_or_none()

        if existing_user:
            continue

        user = User(
            login=user_data["login"],
            hashed_password=get_password_hash(user_data["password"]),
            role=user_data["role"],
            organization_name=organization.name,
            name=user_data["name"],
            surname=user_data["surname"],
            patronymic=user_data["patronymic"],
            date_of_birth=user_data["date_of_birth"],
            is_active=True,
        )
        db.add(user)

    await db.commit()

async def seed_clinical_protocols(db: AsyncSession) -> None:
    try:
        exists = await db.execute(select(ClinicalProtocol).limit(1))
        if exists.first():
            return

        protocols_dir = Path(__file__).resolve().parents[2] / "clinical_protocols"
        if not protocols_dir.is_dir():
            logger.warning("Clinical protocols directory not found. Skipping seed.")
            return

        pdf_files = list(protocols_dir.glob("*.pdf"))
        if not pdf_files:
            return

        now = datetime.now(timezone.utc)
        records = []

        for pdf_path in pdf_files:
            title = pdf_path.stem.replace("_", "-").title()
            file_key = f"clinical_protocols/{pdf_path.name}"
            records.append(ClinicalProtocol(title=title, version="1.0", file_object_key=file_key, status=ClinicalProtocolStatus.UPLOADED,
                                            uploaded_by_user_id=1, uploaded_at=now, updated_at=now))

        db.add_all(records)
        await db.commit()
        logger.info(f"Seeded {len(records)} clinical protocols from {protocols_dir}")
    except Exception as e:
        logger.error(f"Failed to seed clinical protocols: {e}")

async def bootstrap() -> None:
    await create_tables()

    async with AsyncSessionLocal() as db:
        await bootstrap_first_admin(db)
        await seed_clinical_protocols(db)

