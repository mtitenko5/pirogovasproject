from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserLogin
from app.core.security import get_password_hash, verify_password


async def login_user(db: AsyncSession, user_data: UserLogin) -> User:
    result = await db.execute(select(User).where(User.login == user_data.login))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("Invalid login")
    if not verify_password(user_data.password, user.hashed_password):
        raise ValueError("Invalid password")
    return user

def build_fio(user: User) -> str:
    parts = [user.surname, user.name, user.patronymic]
    return " ".join(part for part in parts if part)


async def change_password(
    db,
    user: User,
    old_password: str,
    new_password: str,
) -> None:
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    user.hashed_password = get_password_hash(new_password)
    await db.commit()